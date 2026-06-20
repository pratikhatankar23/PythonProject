import re
import time
from pathlib import Path

from playwright.sync_api import Page

from pageObjects.addYesBankBeneSalary import AddYesBankBeneSalaryPage


class AddDomesticBeneSalaryPage(AddYesBankBeneSalaryPage):
    ADD_EMPLOYEE_ERROR_PATTERN = re.compile(
        r"(employee\s+.*already\s+exists|employee\s+.*already\s+present|"
        r"employee\s+with\s+.*already\s+exists|"
        r"employee\s+with\s+.*already\s+present|"
        r"nickname\s+.*already\s+exists|nickname\s+.*already\s+present|"
        r"invalid\s+ifsc|ifsc\s+.*(?:invalid|not\s+found|does\s+not\s+exist)|"
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

    def add_domestic_bene_salary(self, salary_data):
        try:
            self._handle_post_login_popups()
            self.navigate_to_add_domestic_employee()
            self.enter_domestic_employee_details(salary_data)
            self.verify_review_domestic_employee_details(salary_data)
            self.confirm_review_and_enter_otp(salary_data["otp"])
            self.assert_employee_added_successfully()
        except Exception as exc:
            artifact_dir = self._save_debug_artifacts()
            error_message = str(exc)
            if not isinstance(exc, AssertionError):
                error_message = f"{type(exc).__name__}: {exc}"

            raise AssertionError(
                f"{error_message}\n\nDebug artifacts saved to: {artifact_dir.resolve()}"
            ) from None

    def navigate_to_add_domestic_employee(self):
        self._hover_menu_item("Payments")
        self._hover_menu_item("Salary Management")
        self._click_salary_leaf_menu_item("Add Employee")
        self._wait_for_employee_details_screen(timeout=45)
        self._select_other_banks_employee_type()
        self._wait_for_other_banks_employee_form(timeout=45)

    def enter_domestic_employee_details(self, salary_data):
        account_number, confirm_account_number = self._find_salary_account_fields()
        self._type_like_user(account_number, salary_data["accountNumber"])
        self._type_like_user(
            confirm_account_number,
            salary_data["confirmAccountNumber"],
            verify_value=False,
        )
        confirm_account_number.press("Tab")

        transfer_amount = self._find_transfer_amount_field()
        self._type_like_user(
            transfer_amount,
            salary_data["transferAmount"],
            verify_value=False,
        )

        self._enter_ifsc_and_verify(salary_data["ifsc"])

        account_name = self._find_account_name_field()
        self._type_like_user(account_name, salary_data["accountName"])

        employee_nickname = self._find_employee_nickname_field()
        self._type_like_user(employee_nickname, salary_data["empNickName"])

        employee_id = self._find_employee_id_field()
        self._type_like_user(employee_id, salary_data["empId"])

        email = self._find_email_field()
        self._type_like_user(email, salary_data["emailId"])

        mobile = self._find_mobile_number_field()
        self._type_like_user(mobile, salary_data["mobileNumber"])

        self._click_action(
            re.compile(r"^\s*Proceed\s*$", re.I),
            "Proceed button",
            value_fragments=("Proceed",),
        )
        self._wait_for_review_employee_details_or_fail(timeout=45)

    def verify_review_domestic_employee_details(self, salary_data):
        missing_values = []
        review_text = ""
        deadline = time.monotonic() + 30

        while time.monotonic() < deadline:
            review_text = self._normalized_body_text()
            missing_values = self._missing_review_domestic_employee_values(
                salary_data,
                review_text,
            )

            if not missing_values:
                return

            self.page.wait_for_timeout(500)

        review_text = self._normalized_body_text()
        missing_values = self._missing_review_domestic_employee_values(
            salary_data,
            review_text,
        )

        if missing_values:
            raise AssertionError(
                "Review Employee Details screen is missing expected domestic salary "
                f"value(s): {missing_values}\n\nReview text:\n{review_text}"
            )

    def _missing_review_domestic_employee_values(self, salary_data, review_text):
        amount = salary_data["transferAmount"]
        amount_with_decimal = f"{float(amount):.2f}" if self._is_number(amount) else amount
        expected_value_groups = [
            (salary_data["accountNumber"],),
            (amount, amount_with_decimal, f"INR {amount_with_decimal}"),
            (salary_data["ifsc"],),
            (salary_data["accountName"],),
            (salary_data["empNickName"],),
            (salary_data["empId"],),
            (salary_data["emailId"],),
            (salary_data["mobileNumber"],),
        ]
        missing_values = [
            values
            for values in expected_value_groups
            if not any(self._normalize_text(value) in review_text for value in values)
        ]

        employee_details_pattern = re.compile(
            rf"{re.escape(salary_data['accountName'])}\s*-\s*"
            rf"{re.escape(salary_data['accountNumber'])}",
            re.I,
        )

        if not employee_details_pattern.search(review_text):
            missing_values.append(
                (f"{salary_data['accountName']}-{salary_data['accountNumber']}",)
            )

        return missing_values

    def _select_other_banks_employee_type(self):
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
            "Other Banks employee type option",
        )

        try:
            option.click(timeout=10000)
        except Exception:
            option.evaluate("element => element.click()")

        try:
            self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        self.page.wait_for_timeout(1000)

    def _wait_for_other_banks_employee_form(self, timeout: float = 45):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()
            error_match = self.ADD_EMPLOYEE_ERROR_PATTERN.search(body_text)

            if error_match:
                raise AssertionError(
                    "Other Banks Employee Details screen showed an error: "
                    f"{error_match.group(0)}\n\nPage text:\n{body_text}"
                )

            if re.search(r"\bIFSC(?:\s+Code)?\b", body_text, re.I):
                if self._find_ifsc_field_optional():
                    return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for Other Banks Employee Details form with IFSC "
            f"Code field.\n{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _find_transfer_amount_field(self):
        label = re.compile(r"^\s*(?:Transfer|Salary)\s+Amount\s*$", re.I)

        return self._find_visible_field(
            [
                lambda frame: frame.get_by_label(label),
                lambda frame: frame.get_by_placeholder(label),
                lambda frame: frame.get_by_role("textbox", name=label),
                lambda frame: frame.locator(
                    'input[aria-label*="Transfer Amount" i], '
                    'input[aria-label*="Salary Amount" i], '
                    'input[id*="transfer" i][id*="amount" i], '
                    'input[id*="salary" i][id*="amount" i], '
                    'input[name*="transfer" i][name*="amount" i], '
                    'input[name*="salary" i][name*="amount" i], '
                    'input[id*="amount" i], input[name*="amount" i]'
                ),
            ],
            "Transfer Amount field",
        )

    def _find_account_name_field(self):
        label = re.compile(r"^\s*(?:Account|Employee)\s+Name\s*$", re.I)

        return self._find_visible_field(
            [
                lambda frame: frame.get_by_label(label),
                lambda frame: frame.get_by_placeholder(label),
                lambda frame: frame.get_by_role("textbox", name=label),
                lambda frame: frame.locator(
                    'input[aria-label*="Account Name" i], '
                    'input[aria-label*="Employee Name" i], '
                    'input[id*="account" i][id*="name" i], '
                    'input[id*="employee" i][id*="name" i], '
                    'input[id*="emp" i][id*="name" i], '
                    'input[name*="account" i][name*="name" i], '
                    'input[name*="employee" i][name*="name" i], '
                    'input[name*="emp" i][name*="name" i]'
                ),
            ],
            "Account Name field",
        )

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
            error_match = self.ADD_EMPLOYEE_ERROR_PATTERN.search(body_text)

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

    @staticmethod
    def _is_number(value: str):
        try:
            float(value)
            return True
        except (TypeError, ValueError):
            return False

    def _save_debug_artifacts(self) -> Path:
        artifact_dir = (
            Path("artifacts")
            / f"add_domestic_bene_salary_{time.strftime('%Y%m%d_%H%M%S')}"
        )
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
