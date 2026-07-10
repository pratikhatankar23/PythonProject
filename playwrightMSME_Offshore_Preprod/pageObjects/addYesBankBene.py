import re
import time
from pathlib import Path

from playwright.sync_api import Page


class AddYesBankBenePage:
    ADD_BENEFICIARY_ERROR_PATTERN = re.compile(
        r"(beneficiary\s+with\s+nickname\s+already\s+present|"
        r"payee\s+with\s+this\s+nickname\s+already\s+exists|"
        r"beneficiary\s+.*already\s+exists|"
        r"beneficiary\s+.*already\s+present|"
        r"payee\s+.*already\s+exists|"
        r"payee\s+.*already\s+present)",
        re.I,
    )
    INVALID_ACCOUNT_NAME_PATTERN = re.compile(r"invalid\s+account\s+name", re.I)

    def __init__(self, page: Page):
        self.page = page
        self.console_messages = []
        self.request_failures = []
        self.beneficiary_already_exists = False
        self._capture_debug_events()

    def add_yes_bank_beneficiary(self, bene_data):
        try:
            self.beneficiary_already_exists = False
            self._handle_post_login_popups()
            self.navigate_to_add_beneficiary()
            beneficiary_name = self.enter_beneficiary_details(bene_data)
            if self.beneficiary_already_exists:
                return
            self.verify_review_details(bene_data, beneficiary_name)
            self.confirm_review_and_enter_otp(bene_data["otp"])
            self.assert_beneficiary_added()
        except AssertionError as exc:
            artifact_dir = self._save_debug_artifacts()
            raise AssertionError(
                f"{exc}\n\nDebug artifacts saved to: {artifact_dir.resolve()}"
            ) from None

    def navigate_to_add_beneficiary(self):
        self._hover_menu_item("Payments")
        self._hover_menu_item("Manage Beneficiary")
        self._click_menu_item("Add Beneficiary")
        self._wait_for_add_beneficiary_form(timeout=45)
        self._assert_default_yes_bank_beneficiary_type()

    def enter_beneficiary_details(self, bene_data):
        account_number, confirm_account_number = self._find_internal_account_fields()
        self._type_like_user(account_number, bene_data["accountNumber"])

        self._type_like_user(
            confirm_account_number,
            bene_data["confirmAccountNumber"],
            verify_value=False,
        )
        confirm_account_number.press("Tab")

        beneficiary_name = self._wait_for_beneficiary_name(bene_data["accountNumber"])

        country_code, mobile_number = self._find_mobile_fields()
        self._select_country_code(country_code, bene_data["countryCode"])
        self._type_like_user(mobile_number, bene_data["mobileNumber"])

        email = self._find_input_by_selector(
            'input[aria-label="Email ID"], input[id^="PayeeEmailID"][id$="|input"]',
            "Email ID field",
        )
        self._type_like_user(email, bene_data["emailId"])

        nickname = self._find_input_by_selector(
            'input[aria-label="Nickname"]',
            "Nickname field",
        )
        self._type_like_user(nickname, bene_data["beneNickName"])

        self._click_action(
            re.compile(r"^\s*Proceed\s*$", re.I),
            "Proceed button",
            value_fragments=("Proceed",),
        )
        self._wait_for_review_details_or_fail(timeout=45)

        return beneficiary_name

    def _find_internal_account_fields(self):
        account_number = self._find_input_by_selector(
            'input[id*="_hidden_account_number|input"]',
            "Account Number field",
        )
        confirm_account_number = self._find_input_by_selector(
            'input[id*="_confirm_account_number|input"]',
            "Re-enter Account Number field",
        )

        return account_number, confirm_account_number

    def _find_input_by_selector(self, selector: str, description: str, timeout: float = 30):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                field = self._visible_enabled_first([frame.locator(selector)])

                if field:
                    return field

            self.page.wait_for_timeout(500)

        raise AssertionError(
            f"Could not find {description} using selector {selector!r}.\n"
            f"{self._page_snapshot()}\n\n"
            f"{self._input_snapshot()}"
        )

    def verify_review_details(self, bene_data, beneficiary_name):
        country_code_digits = bene_data["countryCode"].lstrip("+")
        expected_value_groups = [
            (bene_data["accountNumber"],),
            (bene_data["confirmAccountNumber"],),
            (
                bene_data["countryCode"],
                f"{country_code_digits}{bene_data['mobileNumber']}",
            ),
            (bene_data["mobileNumber"],),
            (bene_data["emailId"],),
            (bene_data["beneNickName"],),
        ]

        if beneficiary_name:
            expected_value_groups.append((beneficiary_name,))

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
                "Review Details screen is missing expected value(s): "
                f"{missing_values}\n\nReview text:\n{review_text}"
            )

    def _missing_review_values(self, expected_value_groups, review_text):
        return [
            values
            for values in expected_value_groups
            if not any(
                self._normalize_text(value) in review_text for value in values if value
            )
        ]

    def confirm_review_and_enter_otp(self, otp):
        confirm_and_proceed = re.compile(r"^\s*Confirm\s*(?:and|&)\s*Proceed\s*$", re.I)

        self._click_action(
            confirm_and_proceed,
            "Confirm and Proceed button on Review Details",
            value_fragments=("Confirm", "Proceed"),
        )
        self._fill_otp(otp)
        self._click_action(
            confirm_and_proceed,
            "Confirm and Proceed button on OTP screen",
            value_fragments=("Confirm", "Proceed"),
        )

    def assert_beneficiary_added(self):
        success_text = re.compile(
            r"(Beneficiary\s+added\s+successfully|"
            r"beneficiary\s+has\s+been\s+added\s+successfully|"
            r"successfully\s+added)",
            re.I,
        )
        self._wait_for_final_confirmation_or_fail(success_text, timeout=45)

    def _wait_for_review_details_or_fail(self, timeout: float = 45):
        review_details = re.compile(r"Review\s+Details", re.I)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()
            error_match = self.ADD_BENEFICIARY_ERROR_PATTERN.search(body_text)
            invalid_account_match = self.INVALID_ACCOUNT_NAME_PATTERN.search(body_text)

            if error_match:
                self.beneficiary_already_exists = True
                return

            if invalid_account_match:
                raise AssertionError(
                    "Add Beneficiary failed before Review Details screen because the "
                    "YES BANK account name could not be resolved: "
                    f"{invalid_account_match.group(0)}\n\nPage text:\n{body_text}"
                )

            if review_details.search(body_text):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for Review Details screen after clicking Proceed.\n"
            f"{self._page_snapshot()}"
        )

    def _wait_for_final_confirmation_or_fail(self, success_text, timeout: float = 45):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()
            error_match = self.ADD_BENEFICIARY_ERROR_PATTERN.search(body_text)

            if error_match:
                raise AssertionError(
                    "Add Beneficiary failed before final confirmation screen: "
                    f"{error_match.group(0)}\n\nPage text:\n{body_text}"
                )

            if success_text.search(body_text):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for final Beneficiary Added Successfully confirmation "
            "after OTP submission.\n"
            f"{self._page_snapshot()}"
        )

    def _capture_debug_events(self):
        self.page.on(
            "console",
            lambda msg: self.console_messages.append(f"{msg.type}: {msg.text}"),
        )
        self.page.on(
            "pageerror",
            lambda exc: self.console_messages.append(f"pageerror: {exc}"),
        )
        self.page.on(
            "requestfailed",
            lambda request: self.request_failures.append(
                f"{request.method} {request.url} -> {request.failure}"
            ),
        )

    @staticmethod
    def _visible_first(locators):
        for locator in locators:
            try:
                for index in range(locator.count()):
                    candidate = locator.nth(index)
                    if candidate.is_visible():
                        return candidate
            except Exception:
                continue
        return None

    @staticmethod
    def _visible_enabled_first(locators):
        for locator in locators:
            try:
                for index in range(locator.count()):
                    candidate = locator.nth(index)
                    if candidate.is_visible() and candidate.is_enabled():
                        return candidate
            except Exception:
                continue
        return None

    def _handle_post_login_popups(self):
        try:
            checkbox = self._visible_enabled_first(
                [
                    self.page.locator('input[type="checkbox"][name*="secureConsent" i]'),
                    self.page.locator('input[type="checkbox"][id*="physicalstmt" i]'),
                ]
            )

            if checkbox:
                checkbox.check(timeout=5000)
                self._click_action(
                    re.compile(r"^\s*Proceed\s*$", re.I),
                    "secure usage Proceed button",
                    value_fragments=("Proceed",),
                    timeout=10,
                )
        except Exception:
            pass

        for label in ("OK", "Continue banking", "Stay Connected"):
            try:
                action = self._find_action(
                    re.compile(rf"^\s*{re.escape(label)}\s*$", re.I),
                    f"{label} popup button",
                    value_fragments=(label,),
                    timeout=3,
                )
                action.click(timeout=3000)
            except Exception:
                continue

    def _find_field_by_label(self, label_pattern, description: str, index: int = 0):
        deadline = time.monotonic() + 30

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                field = self._visible_enabled_first(
                    [
                        frame.get_by_label(label_pattern),
                        frame.get_by_placeholder(label_pattern),
                        frame.get_by_role("textbox", name=label_pattern),
                        frame.get_by_role("combobox", name=label_pattern),
                    ]
                )

                if field:
                    return field

                fields = self._nearby_fields(frame, label_pattern)

                if len(fields) > index:
                    return fields[index]

            self.page.wait_for_timeout(500)

        raise AssertionError(
            f"Could not find {description}.\n"
            f"{self._page_snapshot()}\n\n"
            f"{self._input_snapshot()}"
        )

    def _nearby_fields(self, frame, label_pattern):
        results = []
        labels = frame.locator("label, span, div, oj-label")

        try:
            count = labels.count()
        except Exception:
            return results

        for index in range(count):
            label = labels.nth(index)

            try:
                label_text = self._normalize_text(label.inner_text(timeout=300))
            except Exception:
                continue

            if not label_pattern.search(label_text):
                continue

            candidates = label.locator(
                "xpath=following::input[not(@type='hidden') and "
                "not(@type='radio') and not(@type='checkbox')]|"
                "following::textarea|following::*[@role='combobox']"
            )

            try:
                candidate_count = min(candidates.count(), 6)
            except Exception:
                continue

            for candidate_index in range(candidate_count):
                candidate = candidates.nth(candidate_index)

                try:
                    if candidate.is_visible() and candidate.is_enabled():
                        results.append(candidate)
                except Exception:
                    continue

            if results:
                return results

        return results

    def _find_mobile_fields(self):
        deadline = time.monotonic() + 30

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                country = self._visible_enabled_first(
                    [
                        frame.locator('[role="combobox"][id^="oj-select-choice"]'),
                        frame.get_by_role("combobox"),
                    ]
                )
                mobile = self._visible_enabled_first(
                    [
                        frame.locator('input[aria-label*="Mobile Number" i]'),
                        frame.locator('input[type="tel"]'),
                        frame.locator('input[name*="mobile" i]'),
                        frame.locator('input[id*="mobile" i]'),
                    ]
                )

                if country and mobile:
                    return country, mobile

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Could not find Mobile Number country code and mobile input fields.\n"
            f"{self._page_snapshot()}\n\n"
            f"{self._input_snapshot()}"
        )

    def _wait_for_beneficiary_name(self, account_number: str):
        deadline = time.monotonic() + 45

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()
            invalid_account_match = self.INVALID_ACCOUNT_NAME_PATTERN.search(body_text)

            if invalid_account_match:
                raise AssertionError(
                    "Beneficiary name did not populate because the YES BANK account "
                    f"number {account_number!r} is invalid.\n\nPage text:\n{body_text}"
                )

            for frame in self.page.frames:
                fields = [
                    frame.locator('input[id^="AccountName"][id$="|input"]'),
                    frame.locator('input[aria-label*="Beneficiary name" i]'),
                ]

                for field in fields:
                    try:
                        for index in range(field.count()):
                            value = field.nth(index).input_value(timeout=500).strip()

                            if value:
                                return value
                    except Exception:
                        continue

            self.page.wait_for_timeout(1000)

        raise AssertionError(
            "Beneficiary name did not auto-populate for YES BANK account number "
            f"{account_number!r}.\n\n{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _select_country_code(self, country_code_field, country_code: str):
        country_code_field.click(timeout=10000)
        self.page.wait_for_timeout(500)

        search = self._visible_enabled_first(
            [
                self.page.locator(".oj-listbox-search input"),
                self.page.locator('input[aria-label*="Search" i]'),
            ]
        )

        if search:
            search.fill(country_code)
            self.page.wait_for_timeout(500)

        option = self._visible_enabled_first(
            [
                self.page.locator(".oj-listbox-result-label").filter(
                    has_text=re.compile(re.escape(country_code))
                ),
                self.page.locator("[role='option']").filter(
                    has_text=re.compile(re.escape(country_code))
                ),
                self.page.get_by_text(re.compile(re.escape(country_code))),
            ]
        )

        if option:
            option.click(timeout=10000)
        else:
            self.page.keyboard.press("Enter")

        self.page.wait_for_timeout(500)

    def _type_like_user(self, locator, value: str, verify_value: bool = True):
        locator.click(timeout=10000)
        locator.press("Control+A")
        locator.press("Backspace")

        try:
            locator.press_sequentially(value, delay=75)
        except AttributeError:
            locator.type(value, delay=75)

        try:
            actual_value = locator.input_value(timeout=1000)
        except Exception:
            actual_value = value

        is_masked_value = bool(actual_value) and set(actual_value) <= {"*"}

        if verify_value and actual_value != value and not is_masked_value:
            raise AssertionError(
                f"Expected field value to be {value!r}, but browser has {actual_value!r}."
            )

        locator.press("Tab")

    def _input_value_locators(self, frame, fragments):
        locators = []

        for fragment in fragments:
            locators.append(
                frame.locator(
                    f"input[type='button'][value*='{fragment}' i], "
                    f"input[type='submit'][value*='{fragment}' i]"
                )
            )

        return locators

    def _find_action(
        self,
        label_pattern,
        description: str,
        value_fragments=(),
        timeout: float = 30,
    ):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                action = self._visible_enabled_first(
                    [
                        frame.get_by_role("button", name=label_pattern),
                        frame.get_by_role("link", name=label_pattern),
                        frame.get_by_role("menuitem", name=label_pattern),
                        frame.locator("button").filter(has_text=label_pattern),
                        frame.locator("oj-button").filter(has_text=label_pattern),
                        frame.locator("[role='button']").filter(has_text=label_pattern),
                        frame.locator("[role='menuitem']").filter(has_text=label_pattern),
                        frame.locator("a").filter(has_text=label_pattern),
                        *self._input_value_locators(frame, value_fragments),
                    ]
                )

                if action:
                    return action

            self.page.wait_for_timeout(500)

        raise AssertionError(
            f"Could not find {description}.\n"
            f"{self._page_snapshot()}\n\n"
            f"{self._action_snapshot()}"
        )

    def _click_action(self, label_pattern, description: str, value_fragments=(), timeout=30):
        action = self._find_action(
            label_pattern,
            description,
            value_fragments=value_fragments,
            timeout=timeout,
        )

        try:
            action.click(timeout=10000)
        except Exception as exc:
            raise AssertionError(
                f"Found {description}, but click failed: {exc}\n"
                f"{self._page_snapshot()}\n\n"
                f"{self._action_snapshot()}"
            ) from None

    def _click_text(self, label_pattern, description: str):
        self._click_action(label_pattern, description)

        try:
            self.page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass

        self.page.wait_for_timeout(500)

    def _hover_menu_item(self, label: str):
        menu_item = self._find_menu_item(label)

        try:
            menu_item.hover(timeout=10000)
        except Exception:
            menu_item.click(timeout=10000)

        self.page.wait_for_timeout(500)

    def _click_menu_item(self, label: str):
        menu_item = self._find_menu_item(label)

        try:
            menu_item.click(timeout=10000)
        except Exception:
            menu_item.evaluate("element => element.click()")

        try:
            self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        self.page.wait_for_timeout(1000)

    def _find_menu_item(self, label: str, timeout: float = 30):
        label_pattern = re.compile(rf"^\s*{re.escape(label)}\s*$", re.I)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                item = self._visible_enabled_first(
                    [
                        frame.locator(f'li[id="{label}"]'),
                        frame.locator(f'div[alt="{label}"]'),
                        frame.locator("span").filter(has_text=label_pattern),
                        frame.locator("div.text-css1").filter(has_text=label_pattern),
                        frame.locator("div.bordercss").filter(has_text=label_pattern),
                    ]
                )

                if item:
                    return item

            self.page.wait_for_timeout(500)

        raise AssertionError(
            f"Could not find {label} menu item.\n"
            f"{self._page_snapshot()}\n\n"
            f"{self._action_snapshot()}"
        )

    def _fill_otp(self, otp: str):
        otp_fields = self._find_otp_fields(len(otp))

        try:
            if len(otp_fields) == 1:
                self._type_like_user(otp_fields[0], otp, verify_value=False)
                return

            for digit, field in zip(otp, otp_fields):
                self._type_like_user(field, digit, verify_value=False)
        except Exception as exc:
            raise AssertionError(
                f"Found OTP field, but fill failed: {exc}\n"
                f"{self._page_snapshot()}\n\n"
                f"{self._input_snapshot()}"
            ) from None

    def _find_otp_fields(self, otp_length: int, timeout: float = 30):
        otp_text = re.compile(r"(otp|one\s*time|verification|security\s*code)", re.I)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                single_otp = self._visible_enabled_first(
                    [
                        frame.locator('input[name*="otp" i]'),
                        frame.locator('input[id*="otp" i]'),
                        frame.locator('input[placeholder*="otp" i]'),
                        frame.locator('textarea[name*="otp" i]'),
                        frame.locator('textarea[id*="otp" i]'),
                        frame.locator('textarea[placeholder*="otp" i]'),
                        frame.get_by_placeholder(otp_text),
                        frame.get_by_role("textbox", name=otp_text),
                        frame.locator('input[inputmode="numeric"]'),
                        frame.locator('input[type="tel"]'),
                        frame.locator('input[type="number"]'),
                        frame.locator('input[maxlength="6"]'),
                    ]
                )

                if single_otp:
                    return [single_otp]

                otp_fields = []
                fields = frame.locator("input, textarea")

                try:
                    count = fields.count()
                except Exception:
                    continue

                for index in range(count):
                    field = fields.nth(index)

                    try:
                        if not field.is_visible() or not field.is_enabled():
                            continue

                        attrs = field.evaluate(
                            """
                            e => ({
                              type: (e.getAttribute("type") || "").toLowerCase(),
                              id: e.id || "",
                              name: e.getAttribute("name") || "",
                              placeholder: e.getAttribute("placeholder") || "",
                              aria: e.getAttribute("aria-label") || "",
                              autocomplete: e.getAttribute("autocomplete") || "",
                              inputmode: (e.getAttribute("inputmode") || "").toLowerCase(),
                              maxlength: e.getAttribute("maxlength") || ""
                            })
                            """
                        )
                    except Exception:
                        continue

                    if self._looks_like_otp_field(attrs):
                        otp_fields.append(field)

                if len(otp_fields) == 1:
                    return otp_fields

                if len(otp_fields) >= otp_length:
                    return otp_fields[:otp_length]

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Could not find OTP field.\n"
            f"{self._page_snapshot()}\n\n"
            f"{self._input_snapshot()}"
        )

    def _wait_for_page_text(self, pattern, timeout: float = 30):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if pattern.search(self._normalized_body_text()):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            f"Timed out waiting for page text matching {pattern.pattern!r}.\n"
            f"{self._page_snapshot()}"
        )

    def _wait_for_add_beneficiary_form(self, timeout: float = 45):
        deadline = time.monotonic() + timeout
        account_selector = 'input[id*="_hidden_account_number|input"]'
        confirm_selector = 'input[id*="_confirm_account_number|input"]'

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()
            form_has_default_type = "YES BANK" in body_text.upper()

            account_number = None
            confirm_account_number = None

            for frame in self.page.frames:
                account_number = self._visible_enabled_first(
                    [frame.locator(account_selector)]
                )
                confirm_account_number = self._visible_enabled_first(
                    [frame.locator(confirm_selector)]
                )

                if account_number and confirm_account_number and form_has_default_type:
                    return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for Add New Beneficiary form with default YES BANK "
            "beneficiary type.\n"
            f"{self._page_snapshot()}\n\n"
            f"{self._input_snapshot()}"
        )

    def _assert_default_yes_bank_beneficiary_type(self):
        deadline = time.monotonic() + 10

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()

            if "YES BANK" in body_text.upper():
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Expected Beneficiary Type to default to YES BANK, but YES BANK "
            f"was not visible on the Add Beneficiary screen.\n\n{body_text}"
        )

    @staticmethod
    def _looks_like_otp_field(attrs):
        text = " ".join(
            str(attrs.get(key) or "")
            for key in ("id", "name", "placeholder", "aria", "autocomplete")
        )

        return bool(
            re.search(r"(otp|one\s*time|verification|security\s*code)", text, re.I)
            or attrs.get("inputmode") in ("numeric", "decimal")
            or attrs.get("type") in ("tel", "number")
            or attrs.get("maxlength") in ("1", "4", "6")
        )

    def _input_snapshot(self) -> str:
        rows = []
        script = """
        els => els.map((e, idx) => ({
          idx,
          tag: e.tagName.toLowerCase(),
          type: e.getAttribute("type") || "",
          id: e.id || "",
          name: e.getAttribute("name") || "",
          placeholder: e.getAttribute("placeholder") || "",
          aria: e.getAttribute("aria-label") || "",
          value: e.value || "",
          visible: !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length)
        }))
        """

        for frame_index, frame in enumerate(self.page.frames):
            try:
                fields = frame.locator("input, textarea").evaluate_all(script)
            except Exception as exc:
                rows.append(f"frame={frame_index} url={frame.url} unavailable: {exc}")
                continue

            for field in fields:
                rows.append(
                    "frame={frame} url={url} idx={idx} tag={tag} type={type} "
                    "id={id} name={name} placeholder={placeholder} aria={aria} "
                    "value={value} visible={visible}".format(
                        frame=frame_index,
                        url=frame.url,
                        **field,
                    )
                )

        return "\n".join(rows) or "No input or textarea elements were found."

    def _action_snapshot(self) -> str:
        rows = []
        script = """
        els => els.map((e, idx) => ({
          idx,
          tag: e.tagName.toLowerCase(),
          type: e.getAttribute("type") || "",
          id: e.id || "",
          role: e.getAttribute("role") || "",
          value: e.getAttribute("value") || "",
          aria: e.getAttribute("aria-label") || "",
          title: e.getAttribute("title") || "",
          text: (e.innerText || e.textContent || "").trim().replace(/\\s+/g, " "),
          visible: !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length),
          disabled: !!e.disabled || e.getAttribute("aria-disabled") === "true"
        }))
        """
        selector = (
            "button, input[type='button'], input[type='submit'], a, "
            "[role='button'], [role='menuitem'], oj-button"
        )

        for frame_index, frame in enumerate(self.page.frames):
            try:
                actions = frame.locator(selector).evaluate_all(script)
            except Exception as exc:
                rows.append(f"frame={frame_index} url={frame.url} unavailable: {exc}")
                continue

            for action in actions:
                rows.append(
                    "frame={frame} url={url} idx={idx} tag={tag} type={type} "
                    "id={id} role={role} value={value} aria={aria} title={title} "
                    "visible={visible} disabled={disabled} text={text}".format(
                        frame=frame_index,
                        url=frame.url,
                        **action,
                    )
                )

        return "\n".join(rows) or "No action elements were found."

    def _page_snapshot(self) -> str:
        rows = [
            f"url={self.page.url}",
            f"title={self.page.title()}",
            f"frames={len(self.page.frames)}",
        ]

        for frame_index, frame in enumerate(self.page.frames):
            try:
                ready_state = frame.evaluate("document.readyState")
                body_text = frame.locator("body").inner_text(timeout=1000)[:1000]
            except Exception as exc:
                ready_state = f"unavailable: {exc}"
                body_text = ""

            rows.append(
                f"frame={frame_index} url={frame.url} readyState={ready_state} "
                f"bodyText={body_text!r}"
            )

        return "\n".join(rows)

    def _save_debug_artifacts(self) -> Path:
        artifact_dir = Path("artifacts") / f"add_yes_bank_bene_{time.strftime('%Y%m%d_%H%M%S')}"
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

    def _normalized_body_text(self):
        chunks = []

        for frame in self.page.frames:
            try:
                chunks.append(frame.locator("body").inner_text(timeout=1000))
            except Exception:
                continue

        return self._normalize_text("\n".join(chunks))

    @staticmethod
    def _normalize_text(text: str):
        return " ".join(str(text).split()).casefold()
