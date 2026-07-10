import re
import time
from pathlib import Path

from playwright.sync_api import Page

from pageObjects.addYesBankBene import AddYesBankBenePage


class AddYesBankBeneSalaryPage(AddYesBankBenePage):
    ADD_EMPLOYEE_ERROR_PATTERN = re.compile(
        r"(employee\s+.*already\s+exists|employee\s+.*already\s+present|"
        r"employee\s+with\s+.*already\s+exists|"
        r"employee\s+with\s+.*already\s+present|"
        r"nickname\s+.*already\s+exists|nickname\s+.*already\s+present)",
        re.I,
    )

    def __init__(self, page: Page):
        super().__init__(page)

    def add_yes_bank_bene_salary(self, salary_data):
        try:
            self._handle_post_login_popups()
            self.navigate_to_add_employee()
            self.enter_employee_details(salary_data)
            self.verify_review_employee_details(salary_data)
            self.confirm_review_and_enter_otp(salary_data["otp"])
            self.assert_employee_added_successfully()
        except AssertionError as exc:
            artifact_dir = self._save_debug_artifacts()
            raise AssertionError(
                f"{exc}\n\nDebug artifacts saved to: {artifact_dir.resolve()}"
            ) from None

    def navigate_to_add_employee(self):
        self._hover_menu_item("Payments")
        self._hover_menu_item("Salary Management")
        self._click_salary_leaf_menu_item("Add Employee")
        self._wait_for_employee_details_screen(timeout=45)
        self._assert_default_yes_bank_employee_type()

    def enter_employee_details(self, salary_data):
        account_number, confirm_account_number = self._find_salary_account_fields()
        self._type_like_user(account_number, salary_data["accountNumber"])
        self._type_like_user(
            confirm_account_number,
            salary_data["confirmAccountNumber"],
            verify_value=False,
        )
        confirm_account_number.press("Tab")

        employee_name = self._find_employee_name_field()
        self._type_like_user(employee_name, salary_data["empName"])

        salary_amount = self._find_salary_amount_field()
        self._type_like_user(salary_amount, salary_data["salaryAmount"])

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

    def verify_review_employee_details(self, salary_data):
        missing_values = []
        review_text = ""
        deadline = time.monotonic() + 30

        while time.monotonic() < deadline:
            review_text = self._normalized_body_text()
            missing_values = self._missing_review_employee_values(
                salary_data,
                review_text,
            )

            if not missing_values:
                return

            self.page.wait_for_timeout(500)

        review_text = self._normalized_body_text()
        missing_values = self._missing_review_employee_values(
            salary_data,
            review_text,
        )

        if missing_values:
            raise AssertionError(
                "Review Employee Details screen is missing expected value(s): "
                f"{missing_values}\n\nReview text:\n{review_text}"
            )

    def _missing_review_employee_values(self, salary_data, review_text):
        amount = salary_data["salaryAmount"]
        amount_with_decimal = f"{float(amount):.2f}" if self._is_number(amount) else amount
        expected_value_groups = [
            (salary_data["accountNumber"],),
            (salary_data["empName"],),
            (amount, amount_with_decimal, f"INR {amount_with_decimal}"),
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
            rf"{re.escape(salary_data['empName'])}\s*-\s*"
            rf"{re.escape(salary_data['accountNumber'])}",
            re.I,
        )

        if not employee_details_pattern.search(review_text):
            missing_values.append(
                (f"{salary_data['empName']}-{salary_data['accountNumber']}",)
            )

        return missing_values

    def assert_employee_added_successfully(self):
        success_text = re.compile(
            r"(Employee\s+Added\s+Successfully|"
            r"Employee\s+added\s+successfully|"
            r"employee\s+has\s+been\s+added\s+successfully)",
            re.I,
        )
        self._wait_for_employee_final_confirmation_or_fail(success_text, timeout=45)

    def _click_salary_leaf_menu_item(self, label: str, timeout: float = 30):
        label_pattern = re.compile(rf"^\s*{re.escape(label)}\s*$", re.I)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                menu_item = self._visible_enabled_first(
                    [
                        frame.locator("li.level-1 span").filter(has_text=label_pattern),
                        frame.locator("li.level-1 div.text-css1").filter(
                            has_text=label_pattern
                        ),
                        frame.locator("ul.innersubmenucssnew li span").filter(
                            has_text=label_pattern
                        ),
                        frame.locator("span").filter(has_text=label_pattern),
                        frame.locator("div.text-css1").filter(has_text=label_pattern),
                    ]
                )

                if not menu_item:
                    continue

                try:
                    menu_item.click(timeout=10000)
                except Exception:
                    menu_item.evaluate("element => element.click()")

                try:
                    self.page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass

                self.page.wait_for_timeout(1000)
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            f"Could not find {label} submenu item under Salary Management.\n"
            f"{self._page_snapshot()}\n\n{self._action_snapshot()}"
        )

    def _wait_for_employee_details_screen(self, timeout: float = 45):
        screen_pattern = re.compile(
            r"(Employee\s+Details|Add\s+Employee|Employee\s+Type)",
            re.I,
        )
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()

            if self.ADD_EMPLOYEE_ERROR_PATTERN.search(body_text):
                raise AssertionError(
                    "Add Employee screen showed an employee error:\n"
                    f"{body_text}"
                )

            if screen_pattern.search(body_text) and re.search(
                r"Account\s+Number",
                body_text,
                re.I,
            ):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for Employee Details screen after clicking "
            f"Add Employee.\n{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _assert_default_yes_bank_employee_type(self):
        body_text = self._normalized_body_text()

        if not re.search(r"\bYES\s+BANK\b", body_text, re.I):
            raise AssertionError(
                "Expected Employee Type to remain selected as YES BANK, but YES BANK "
                f"was not visible on the Employee Details screen.\n\n{body_text}"
            )

    def _wait_for_review_employee_details_or_fail(self, timeout: float = 45):
        review_pattern = re.compile(r"Review\s+Employee\s+Details", re.I)
        fallback_review_pattern = re.compile(r"Review\s+Details", re.I)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()
            error_match = self.ADD_EMPLOYEE_ERROR_PATTERN.search(body_text)

            if error_match:
                raise AssertionError(
                    "Add Employee failed before Review Employee Details screen: "
                    f"{error_match.group(0)}\n\nPage text:\n{body_text}"
                )

            if review_pattern.search(body_text):
                return

            if fallback_review_pattern.search(body_text) and re.search(
                r"\bEmployee\b",
                body_text,
                re.I,
            ):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for Review Employee Details screen after clicking "
            f"Proceed.\n{self._page_snapshot()}"
        )

    def _wait_for_employee_final_confirmation_or_fail(self, success_text, timeout: float = 45):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()
            error_match = self.ADD_EMPLOYEE_ERROR_PATTERN.search(body_text)

            if error_match:
                raise AssertionError(
                    "Add Employee failed before final confirmation screen: "
                    f"{error_match.group(0)}\n\nPage text:\n{body_text}"
                )

            if success_text.search(body_text):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for Employee Added Successfully confirmation "
            f"after OTP submission.\n{self._page_snapshot()}"
        )

    def _find_salary_account_fields(self):
        account_label = re.compile(r"^\s*(?:Employee\s+)?Account\s+Number\s*$", re.I)
        confirm_label = re.compile(
            r"^\s*(?:Re-enter|Confirm)\s+(?:Employee\s+)?Account\s+Number\s*$",
            re.I,
        )

        account_number = self._find_visible_field(
            [
                lambda frame: frame.locator('input[id*="_hidden_account_number|input"]'),
                lambda frame: frame.locator(
                    'input[aria-label="Account Number" i], '
                    'input[aria-label="Employee Account Number" i], '
                    'input[id*="account" i][id*="number" i]'
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

    def _find_employee_name_field(self):
        label = re.compile(r"^\s*Employee\s+Name\s*$", re.I)

        return self._find_visible_field(
            [
                lambda frame: frame.get_by_label(label),
                lambda frame: frame.get_by_placeholder(label),
                lambda frame: frame.get_by_role("textbox", name=label),
                lambda frame: frame.locator(
                    'input[aria-label*="Employee Name" i], '
                    'input[id*="employee" i][id*="name" i], '
                    'input[id*="emp" i][id*="name" i], '
                    'input[name*="employee" i][name*="name" i], '
                    'input[name*="emp" i][name*="name" i]'
                ),
            ],
            "Employee Name field",
        )

    def _find_salary_amount_field(self):
        label = re.compile(r"^\s*Salary\s+Amount\s*$", re.I)

        return self._find_visible_field(
            [
                lambda frame: frame.get_by_label(label),
                lambda frame: frame.get_by_placeholder(label),
                lambda frame: frame.get_by_role("textbox", name=label),
                lambda frame: frame.locator(
                    'input[aria-label*="Salary Amount" i], '
                    'input[id*="salary" i][id*="amount" i], '
                    'input[name*="salary" i][name*="amount" i], '
                    'input[id*="amount" i], input[name*="amount" i]'
                ),
            ],
            "Salary Amount field",
        )

    def _find_employee_nickname_field(self):
        label = re.compile(r"^\s*Employee\s+Nickname\s*$", re.I)

        return self._find_visible_field(
            [
                lambda frame: frame.get_by_label(label),
                lambda frame: frame.get_by_placeholder(label),
                lambda frame: frame.get_by_role("textbox", name=label),
                lambda frame: frame.locator(
                    'input[aria-label*="Employee Nickname" i], '
                    'input[aria-label*="Nickname" i], '
                    'input[id*="employee" i][id*="nick" i], '
                    'input[id*="emp" i][id*="nick" i], '
                    'input[id*="nickname" i], input[name*="nickname" i]'
                ),
            ],
            "Employee Nickname field",
        )

    def _find_employee_id_field(self):
        label = re.compile(r"^\s*Employee\s+I[Dd]\s*$", re.I)

        return self._find_visible_field(
            [
                lambda frame: frame.get_by_label(label),
                lambda frame: frame.get_by_placeholder(label),
                lambda frame: frame.get_by_role("textbox", name=label),
                lambda frame: frame.locator(
                    'input[aria-label*="Employee Id" i], '
                    'input[aria-label*="Employee ID" i], '
                    'input[id*="employee" i][id*="id" i], '
                    'input[id*="emp" i][id*="id" i], '
                    'input[name*="employee" i][name*="id" i], '
                    'input[name*="emp" i][name*="id" i]'
                ),
            ],
            "Employee Id field",
        )

    def _find_email_field(self):
        label = re.compile(r"^\s*Email\s+ID\s*$", re.I)

        return self._find_visible_field(
            [
                lambda frame: frame.get_by_label(label),
                lambda frame: frame.get_by_placeholder(label),
                lambda frame: frame.get_by_role("textbox", name=label),
                lambda frame: frame.locator(
                    'input[aria-label="Email ID" i], '
                    'input[id^="PayeeEmailID"][id$="|input"], '
                    'input[id*="email" i], input[name*="email" i]'
                ),
            ],
            "Email ID field",
        )

    def _find_mobile_number_field(self):
        label = re.compile(r"^\s*Mobile\s+[Nn]umber\s*$", re.I)

        return self._find_visible_field(
            [
                lambda frame: frame.get_by_label(label),
                lambda frame: frame.get_by_placeholder(label),
                lambda frame: frame.get_by_role("textbox", name=label),
                lambda frame: frame.locator(
                    'input[aria-label*="Mobile Number" i], '
                    'input[aria-label*="Mobile number" i], '
                    'input[id*="mobile" i], input[name*="mobile" i], '
                    'input[type="tel"]'
                ),
            ],
            "Mobile number field",
        )

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

    @staticmethod
    def _is_number(value: str):
        try:
            float(value)
            return True
        except (TypeError, ValueError):
            return False

    def _save_debug_artifacts(self) -> Path:
        artifact_dir = Path("artifacts") / f"add_yes_bank_bene_salary_{time.strftime('%Y%m%d_%H%M%S')}"
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
