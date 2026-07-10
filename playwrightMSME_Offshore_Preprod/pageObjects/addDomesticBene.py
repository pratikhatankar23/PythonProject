import re
import time
from pathlib import Path

from playwright.sync_api import Page

from pageObjects.addYesBankBene import AddYesBankBenePage


class AddDomesticBenePage(AddYesBankBenePage):
    IFSC_ERROR_PATTERN = re.compile(
        r"(invalid\s+ifsc|ifsc\s+.*(?:invalid|not\s+found|does\s+not\s+exist)|"
        r"please\s+enter\s+(?:a\s+)?valid\s+ifsc|could\s+not\s+verify|"
        r"verification\s+failed|unable\s+to\s+verify)",
        re.I,
    )
    SUCCESS_ICON_SELECTOR = (
        "img[src*='success' i], img[src*='tick' i], img[src*='check' i], "
        "img[src*='verified' i], img[alt*='success' i], img[alt*='tick' i], "
        "img[alt*='check' i], img[alt*='verified' i], "
        "[aria-label*='success' i], [aria-label*='verified' i], "
        "[title*='success' i], [title*='verified' i], "
        "[class*='success' i], [class*='tick' i], [class*='check' i], "
        "[class*='verified' i]"
    )

    def __init__(self, page: Page):
        super().__init__(page)

    def add_domestic_beneficiary(self, bene_data):
        try:
            self._handle_post_login_popups()
            self.navigate_to_add_domestic_beneficiary()
            self.enter_domestic_beneficiary_details(bene_data)
            self.verify_review_details(bene_data)
            self.confirm_review_and_enter_otp(bene_data["otp"])
            self.assert_beneficiary_added()
        except AssertionError as exc:
            artifact_dir = self._save_debug_artifacts()
            raise AssertionError(
                f"{exc}\n\nDebug artifacts saved to: {artifact_dir.resolve()}"
            ) from None

    def navigate_to_add_domestic_beneficiary(self):
        self._hover_menu_item("Payments")
        self._hover_menu_item("Manage Beneficiary")
        self._click_menu_item("Add Beneficiary")
        self._wait_for_page_text(
            re.compile(r"Add\s+(?:New\s+)?Beneficiary", re.I),
            timeout=30,
        )
        self._select_other_banks_beneficiary_type()

    def enter_domestic_beneficiary_details(self, bene_data):
        beneficiary_name = self._find_beneficiary_name_field()
        self._type_like_user(beneficiary_name, bene_data["beneficiaryName"])

        country_code, mobile_number = self._find_mobile_fields()
        self._select_country_code(country_code, bene_data["countryCode"])
        self._type_like_user(mobile_number, bene_data["mobileNumber"])

        account_number, confirm_account_number = self._find_domestic_account_fields()
        self._type_like_user(account_number, bene_data["accountNumber"])
        self._type_like_user(
            confirm_account_number,
            bene_data["confirmAccountNumber"],
            verify_value=False,
        )

        self._enter_ifsc_and_verify(bene_data["ifsc"])

        email = self._find_visible_field(
            [
                lambda frame: frame.locator(
                    'input[aria-label="Email ID" i], '
                    'input[id^="PayeeEmailID"][id$="|input"], '
                    'input[id*="email" i], input[name*="email" i]'
                ),
                lambda frame: frame.get_by_label(re.compile(r"Email\s*ID", re.I)),
                lambda frame: frame.get_by_role(
                    "textbox",
                    name=re.compile(r"Email\s*ID", re.I),
                ),
            ],
            "Email ID field",
        )
        self._type_like_user(email, bene_data["emailId"])

        nickname = self._find_visible_field(
            [
                lambda frame: frame.locator('input[aria-label="Nickname" i]'),
                lambda frame: frame.locator(
                    'input[id*="nickname" i], input[name*="nickname" i]'
                ),
                lambda frame: frame.get_by_label(
                    re.compile(r"^\s*Nickname\s*$", re.I)
                ),
                lambda frame: frame.get_by_role(
                    "textbox",
                    name=re.compile(r"^\s*Nickname\s*$", re.I),
                ),
            ],
            "Nickname field",
        )
        self._type_like_user(nickname, bene_data["beneNickName"])

        self._click_action(
            re.compile(r"^\s*Proceed\s*$", re.I),
            "Proceed button",
            value_fragments=("Proceed",),
        )
        self._wait_for_review_details_or_fail(timeout=45)

    def verify_review_details(self, bene_data):
        country_code_digits = bene_data["countryCode"].lstrip("+")
        expected_value_groups = [
            (bene_data["beneficiaryName"],),
            (bene_data["accountNumber"],),
            (bene_data["ifsc"],),
            (
                bene_data["countryCode"],
                f"{country_code_digits}{bene_data['mobileNumber']}",
            ),
            (bene_data["mobileNumber"],),
            (bene_data["emailId"],),
            (bene_data["beneNickName"],),
        ]

        deadline = time.monotonic() + 30
        review_text = ""
        missing_values = expected_value_groups

        while time.monotonic() < deadline:
            review_text = self._normalized_body_text()
            missing_values = self._missing_review_values(
                expected_value_groups, review_text
            )
            if not missing_values:
                return
            self.page.wait_for_timeout(500)

        review_text = self._normalized_body_text()
        missing_values = self._missing_review_values(expected_value_groups, review_text)

        if missing_values:
            raise AssertionError(
                "Review Details screen is missing expected domestic beneficiary "
                f"value(s): {missing_values}\n\nReview text:\n{review_text}"
            )

    def _missing_review_values(self, expected_value_groups, review_text):
        return [
            values
            for values in expected_value_groups
            if not any(
                self._normalize_text(value) in review_text for value in values if value
            )
        ]

    def _select_other_banks_beneficiary_type(self):
        option = self._find_visible_field(
            [
                lambda frame: frame.locator("#GENERICDOMESTIC"),
                lambda frame: frame.locator('[id="GENERICDOMESTIC"]'),
                lambda frame: frame.get_by_role(
                    "link",
                    name=re.compile(r"^\s*Other\s+Banks\s*$", re.I),
                ),
                lambda frame: frame.get_by_role(
                    "button",
                    name=re.compile(r"^\s*Other\s+Banks\s*$", re.I),
                ),
                lambda frame: frame.get_by_role(
                    "tab",
                    name=re.compile(r"^\s*Other\s+Banks\s*$", re.I),
                ),
                lambda frame: frame.locator("a").filter(
                    has_text=re.compile(r"^\s*Other\s+Banks\s*$", re.I)
                ),
                lambda frame: frame.locator("span, div").filter(
                    has_text=re.compile(r"^\s*Other\s+Banks\s*$", re.I)
                ),
            ],
            "Other Banks beneficiary type option",
        )

        try:
            option.click(timeout=10000)
        except Exception:
            option.evaluate("element => element.click()")

        try:
            self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        self._wait_for_domestic_form()

    def _wait_for_domestic_form(self, timeout: float = 45):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()

            if self.IFSC_ERROR_PATTERN.search(body_text):
                raise AssertionError(
                    f"Domestic beneficiary screen showed IFSC error:\n{body_text}"
                )

            if re.search(r"\bIFSC(?:\s+Code)?\b", body_text, re.I):
                if self._find_ifsc_field_optional():
                    return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for Other Banks domestic beneficiary form with IFSC "
            f"Code field.\n{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _find_beneficiary_name_field(self):
        label = re.compile(r"^\s*Beneficiary\s+Name\s*$", re.I)

        return self._find_visible_field(
            [
                lambda frame: frame.get_by_label(label),
                lambda frame: frame.get_by_placeholder(label),
                lambda frame: frame.get_by_role("textbox", name=label),
                lambda frame: frame.locator(
                    'input[aria-label*="Beneficiary" i][aria-label*="Name" i], '
                    'input[id^="AccountName"][id$="|input"], '
                    'input[id*="beneficiary" i][id*="name" i], '
                    'input[id*="payee" i][id*="name" i]'
                ),
            ],
            "Beneficiary Name field",
        )

    def _find_domestic_account_fields(self):
        account_label = re.compile(r"^\s*Account\s+Number\s*$", re.I)
        confirm_label = re.compile(
            r"^\s*(?:Re-enter|Confirm)\s+Account\s+Number\s*$",
            re.I,
        )

        account_number = self._find_visible_field(
            [
                lambda frame: frame.locator(
                    'input[id*="_hidden_account_number|input"], '
                    'input[aria-label="Account Number" i], '
                    'input[aria-label*="Account Number" i]'
                    ':not([aria-label*="Re-enter" i])'
                    ':not([aria-label*="Confirm" i]), '
                    'input[id*="account" i][id*="number" i]'
                    ':not([id*="confirm" i]):not([type="hidden"])'
                ),
                lambda frame: frame.get_by_label(account_label),
                lambda frame: frame.get_by_role("textbox", name=account_label),
            ],
            "Account Number field",
        )
        confirm_account_number = self._find_visible_field(
            [
                lambda frame: frame.locator(
                    'input[id*="_confirm_account_number|input"], '
                    'input[aria-label*="Re-enter" i][aria-label*="Account" i], '
                    'input[aria-label*="Confirm" i][aria-label*="Account" i], '
                    'input[id*="confirm" i][id*="account" i]'
                ),
                lambda frame: frame.get_by_label(confirm_label),
                lambda frame: frame.get_by_role("textbox", name=confirm_label),
            ],
            "Re-enter Account Number field",
        )

        return account_number, confirm_account_number

    def _enter_ifsc_and_verify(self, ifsc: str):
        ifsc_field = self._find_ifsc_field()
        self._type_like_user(ifsc_field, ifsc)
        self._click_action(
            re.compile(r"^\s*Verify\s*$", re.I),
            "Verify IFSC button",
            value_fragments=("Verify",),
            timeout=30,
        )
        self._assert_ifsc_verified(ifsc_field)

    def _find_ifsc_field(self):
        field = self._find_ifsc_field_optional()

        if field:
            return field

        raise AssertionError(
            "Could not find IFSC Code field.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _find_ifsc_field_optional(self):
        label = re.compile(r"^\s*IFSC(?:\s+Code)?\s*$", re.I)

        return self._find_visible_field_optional(
            [
                lambda frame: frame.get_by_label(label),
                lambda frame: frame.get_by_placeholder(label),
                lambda frame: frame.get_by_role("textbox", name=label),
                lambda frame: frame.locator(
                    'input[aria-label*="IFSC" i], input[id*="ifsc" i], '
                    'input[name*="ifsc" i], input[title*="IFSC" i]'
                ),
            ]
        )

    def _assert_ifsc_verified(self, ifsc_field, timeout: float = 30):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()
            error_match = self.IFSC_ERROR_PATTERN.search(body_text)

            if error_match:
                raise AssertionError(
                    "IFSC verification failed after clicking Verify: "
                    f"{error_match.group(0)}\n\nPage text:\n{body_text}"
                )

            if self._has_visible_ifsc_success_indicator(ifsc_field):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Green checkbox / success indicator was not displayed after IFSC "
            f"verification.\n{self._page_snapshot()}\n\n{self._action_snapshot()}"
        )

    def _has_visible_ifsc_success_indicator(self, ifsc_field):
        scopes = []

        for xpath in (
            "xpath=ancestor::*[contains(translate(@class, "
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'ifsc')][1]",
            "xpath=ancestor::*[self::div or self::oj-form-layout][1]",
            "xpath=ancestor::*[self::div or self::oj-form-layout][2]",
        ):
            try:
                scopes.append(ifsc_field.locator(xpath))
            except Exception:
                continue

        scopes.append(self.page.locator("body"))

        for scope in scopes:
            try:
                indicator = self._visible_first([scope.locator(self.SUCCESS_ICON_SELECTOR)])

                if indicator:
                    return True
            except Exception:
                continue

        return False

    def _find_visible_field(self, locator_factories, description: str, timeout: float = 30):
        field = self._find_visible_field_optional(locator_factories, timeout=timeout)

        if field:
            return field

        raise AssertionError(
            f"Could not find {description}.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _find_visible_field_optional(self, locator_factories, timeout: float = 1):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                locators = []

                for factory in locator_factories:
                    try:
                        locators.append(factory(frame))
                    except Exception:
                        continue

                field = self._visible_enabled_first(locators)

                if field:
                    return field

            self.page.wait_for_timeout(200)

        return None

    def _save_debug_artifacts(self) -> Path:
        artifact_dir = Path("artifacts") / f"add_domestic_bene_{time.strftime('%Y%m%d_%H%M%S')}"
        artifact_dir.mkdir(parents=True, exist_ok=True)

        self.page.screenshot(path=artifact_dir / "page.png", full_page=True)
        (artifact_dir / "snapshot.txt").write_text(
            "\n\n".join(
                [
                    "PAGE",
                    self._page_snapshot(),
                    "INPUTS",
                    self._input_snapshot(),
                    "ACTIONS",
                    self._action_snapshot(),
                    "CONSOLE",
                    "\n".join(self.console_messages) or "No console messages captured.",
                    "REQUEST FAILURES",
                    "\n".join(self.request_failures) or "No request failures captured.",
                ]
            ),
            encoding="utf-8",
        )

        for frame_index, frame in enumerate(self.page.frames):
            try:
                (artifact_dir / f"frame_{frame_index}.html").write_text(
                    frame.content(),
                    encoding="utf-8",
                )
            except Exception as exc:
                (artifact_dir / f"frame_{frame_index}.error.txt").write_text(
                    str(exc),
                    encoding="utf-8",
                )

        return artifact_dir
