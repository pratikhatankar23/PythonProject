import re
import time
from pathlib import Path

from playwright.sync_api import Page

from pageObjects.neftRegPayeeOnetime import NeftRegPayeeOnetimePage


class PaySalaryInternalBenePage(NeftRegPayeeOnetimePage):
    NO_RECORDS_PATTERN = re.compile(
        r"(no\s+records?\s+found|no\s+employees?\s+found|"
        r"no\s+results?\s+found|no\s+data\s+found|"
        r"no\s+data\s+to\s+display)",
        re.I,
    )
    SALARY_PAYMENT_ERROR_PATTERN = re.compile(
        r"(salary\s+payment\s+failed|payment\s+failed|transaction\s+failed|"
        r"transfer\s+failed|unable\s+to\s+process|insufficient\s+balance|"
        r"invalid\s+amount|please\s+select|daily\s+limit|"
        r"employee\s+not\s+found)",
        re.I,
    )
    SALARY_PAYMENT_SUCCESS_PATTERN = re.compile(
        r"(Congratulations!?\s+Salary\s+payment\s+to\s+.*"
        r"has\s+gone\s+through\s+successfully|"
        r"Salary\s+payment\s+to\s+.*has\s+gone\s+through\s+successfully|"
        r"Salary\s+payment\s+.*successfully|"
        r"Payment\s+successful|Transaction\s+successful)",
        re.I,
    )

    def __init__(self, page: Page):
        super().__init__(page)

    def pay_salary_internal_bene(self, salary_data):
        try:
            self._handle_post_login_popups()
            self.navigate_to_manage_employee()
            self.click_pay_employee_quick_action()
            self.enter_pay_employee_details(salary_data)
            self.verify_transaction_summary(salary_data)
            self.proceed_to_pay_and_confirm_if_required(salary_data.get("otp"))
            self.assert_salary_payment_successful()
        except Exception as exc:
            artifact_dir = self._save_debug_artifacts()
            error_message = str(exc)
            if not isinstance(exc, AssertionError):
                error_message = f"{type(exc).__name__}: {exc}"

            raise AssertionError(
                f"{error_message}\n\nDebug artifacts saved to: {artifact_dir.resolve()}"
            ) from None

    def navigate_to_manage_employee(self):
        self._hover_menu_item("Payments")
        self._hover_menu_item("Salary Management")
        self._click_salary_leaf_menu_item("Manage Employee")
        self._wait_for_manage_employees_page(timeout=45)
        self._wait_for_employee_list_ready(timeout=30)

        if self._has_no_records_message():
            raise AssertionError("No employee records found on Manage Employees screen.")

        if not self._has_any_employee_record():
            raise AssertionError(
                "Manage Employees screen did not show any employee records.\n"
                f"{self._page_snapshot()}\n\n{self._employee_snapshot()}"
            )

    def click_pay_employee_quick_action(self):
        self._wait_for_quick_actions_section(timeout=30)
        action = self._find_pay_employee_quick_action(timeout=30)
        self._click_quick_action(action, "Pay Employee quick action")

        try:
            self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        self.page.wait_for_timeout(1000)
        self._wait_for_pay_employee_screen(timeout=45)

    def enter_pay_employee_details(self, salary_data):
        self._select_employee(salary_data["employeeName"])
        self._select_salary_transfer_from_account(salary_data["fromAccount"])

        amount = self._find_transfer_amount_field()
        self._type_like_user(amount, salary_data["amount"], verify_value=False)

        remarks = self._find_remarks_field()
        self._type_like_user(remarks, salary_data["remarks"])

        self._click_action(
            re.compile(r"^\s*Proceed\s*$", re.I),
            "Proceed button",
            value_fragments=("Proceed",),
        )
        self._wait_for_transaction_summary_screen(timeout=45)

    def verify_transaction_summary(self, salary_data):
        deadline = time.monotonic() + 30
        missing_values = []
        summary_text = ""

        while time.monotonic() < deadline:
            summary_text = self._normalized_body_text()
            missing_values = self._missing_transaction_summary_values(
                salary_data,
                summary_text,
            )

            if not missing_values and self._employee_details_present():
                return

            self.page.wait_for_timeout(500)

        summary_text = self._normalized_body_text()
        missing_values = self._missing_transaction_summary_values(
            salary_data,
            summary_text,
        )

        if not self._employee_details_present():
            missing_values.append(("Employee Details with a value",))

        if missing_values:
            raise AssertionError(
                "Transaction Summary screen is missing expected salary payment "
                f"value(s): {missing_values}\n\nSummary text:\n{summary_text}"
            )

    def proceed_to_pay_and_confirm_if_required(self, otp: str | None):
        self._click_action(
            re.compile(r"^\s*Proceed\s+to\s+Pay\s*$", re.I),
            "Proceed to Pay button",
            value_fragments=("Proceed", "Pay"),
            timeout=30,
        )

        if self._salary_payment_success_visible(timeout=5):
            return

        if not otp:
            return

        try:
            self._find_otp_fields(len(otp), timeout=5)
        except AssertionError:
            if self._salary_payment_success_visible(timeout=5):
                return
            return

        self._fill_otp(otp)
        self._click_action(
            self.CONFIRM_AND_PROCEED_PATTERN,
            "Confirm and Proceed button on OTP popup",
            value_fragments=("Confirm", "Proceed"),
            timeout=30,
        )

    def assert_salary_payment_successful(self):
        self._wait_for_salary_payment_final_confirmation_or_fail(
            self.SALARY_PAYMENT_SUCCESS_PATTERN,
            timeout=45,
        )

    def _click_salary_leaf_menu_item(self, label: str, timeout: float = 30):
        label_pattern = re.compile(rf"^\s*{re.escape(label)}s?\s*$", re.I)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                menu_item = self._visible_enabled_first(
                    [
                        frame.locator("li.level-1 span").filter(
                            has_text=label_pattern
                        ),
                        frame.locator("li.level-1 div.text-css1").filter(
                            has_text=label_pattern
                        ),
                        frame.locator("ul.innersubmenucssnew li span").filter(
                            has_text=label_pattern
                        ),
                        frame.locator("ul#innermenufield li span").filter(
                            has_text=label_pattern
                        ),
                        frame.locator("span").filter(has_text=label_pattern),
                        frame.locator("div.text-css1").filter(
                            has_text=label_pattern
                        ),
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

    def _wait_for_manage_employees_page(self, timeout: float = 45):
        screen_pattern = re.compile(
            r"(Manage\s+Employees?|Search\s+Employees?|Employee\s+Name|"
            r"Employee\s+ID|Employee\s+Details|Quick\s+Actions)",
            re.I,
        )
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            current_url = self.page.url.lower()
            body_text = self._normalized_body_text()

            if "employee" in current_url or screen_pattern.search(body_text):
                if (
                    self.NO_RECORDS_PATTERN.search(body_text)
                    or self._has_any_employee_record()
                    or self._find_employee_search_field_optional()
                    or re.search(r"Pay\s+Employee", body_text, re.I)
                ):
                    return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for Manage Employees screen.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _wait_for_employee_list_ready(self, timeout: float = 30):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if self._has_no_records_message() or self._has_any_employee_record():
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for employee records or no-records message on "
            "Manage Employees screen.\n"
            f"{self._page_snapshot()}\n\n{self._employee_snapshot()}"
        )

    def _has_no_records_message(self):
        return bool(self.NO_RECORDS_PATTERN.search(self._normalized_body_text()))

    def _has_any_employee_record(self):
        for frame in self.page.frames:
            for rows in self._record_locators(frame):
                try:
                    count = rows.count()
                except Exception:
                    continue

                for index in range(count):
                    row = rows.nth(index)

                    try:
                        if not row.is_visible(timeout=300):
                            continue

                        row_text = row.inner_text(timeout=300)
                    except Exception:
                        continue

                    if self._looks_like_employee_record(row_text):
                        return True

        return False

    def _looks_like_employee_record(self, text: str):
        normalized = self._normalize_text(text)

        if not normalized or self.NO_RECORDS_PATTERN.search(normalized):
            return False

        non_record_patterns = [
            r"^manage\s+employees?$",
            r"^quick\s+actions?$",
            r"^pay\s+employee$",
            r"^search\s+employees?$",
            r"^employee\s+name$",
            r"^employee\s+id$",
        ]

        if any(re.fullmatch(pattern, normalized, re.I) for pattern in non_record_patterns):
            return False

        return bool(re.search(r"(emp|employee|account|\d{3,})", normalized, re.I))

    def _wait_for_quick_actions_section(self, timeout: float = 30):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()

            if re.search(r"Quick\s+Actions", body_text, re.I) and re.search(
                r"Pay\s+Employee",
                body_text,
                re.I,
            ):
                return

            if self._find_pay_employee_quick_action(timeout=1):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Could not find Pay Employee option under Quick Actions on Manage "
            f"Employees screen.\n{self._page_snapshot()}\n\n{self._action_snapshot()}"
        )

    def _find_pay_employee_quick_action(self, timeout: float = 30):
        pay_employee_pattern = re.compile(r"^\s*Pay\s+Employee\s*$", re.I)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                action = self._visible_enabled_first(
                    [
                        frame.get_by_role("button", name=pay_employee_pattern),
                        frame.get_by_role("link", name=pay_employee_pattern),
                        frame.get_by_role("menuitem", name=pay_employee_pattern),
                        frame.locator("button").filter(
                            has_text=pay_employee_pattern
                        ),
                        frame.locator("oj-button").filter(
                            has_text=pay_employee_pattern
                        ),
                        frame.locator("[role='button']").filter(
                            has_text=pay_employee_pattern
                        ),
                        frame.locator("[role='menuitem']").filter(
                            has_text=pay_employee_pattern
                        ),
                        frame.locator("a").filter(has_text=pay_employee_pattern),
                    ]
                )

                if action:
                    return action

                action = self._find_visible_exact_text(
                    frame,
                    "a, button, oj-button, [role='button'], [role='menuitem'], "
                    "span, div",
                    pay_employee_pattern,
                )

                if action:
                    return action

            self.page.wait_for_timeout(500)

        return None

    def _find_visible_exact_text(self, frame, selector: str, label_pattern):
        candidates = frame.locator(selector)

        try:
            count = candidates.count()
        except Exception:
            return None

        for index in range(count):
            candidate = candidates.nth(index)

            try:
                if not candidate.is_visible(timeout=300):
                    continue

                text = candidate.inner_text(timeout=300)
            except Exception:
                continue

            if label_pattern.fullmatch(text.strip()):
                return candidate

        return None

    def _click_quick_action(self, action, description: str):
        if not action:
            raise AssertionError(
                f"Could not find {description}.\n"
                f"{self._page_snapshot()}\n\n{self._action_snapshot()}"
            )

        try:
            action.click(timeout=10000, force=True)
            return
        except Exception:
            pass

        try:
            action.evaluate(
                """
                element => {
                  const clickable = element.closest(
                    "a, button, oj-button, [role='button'], [role='menuitem'], li, div"
                  ) || element;
                  clickable.dispatchEvent(new MouseEvent(
                    "click",
                    { bubbles: true, cancelable: true, view: window }
                  ));
                }
                """
            )
        except Exception as exc:
            raise AssertionError(f"Could not click {description}: {exc}") from None

    def _wait_for_pay_employee_screen(self, timeout: float = 45):
        screen_pattern = re.compile(
            r"(Pay\s+Employee|Select\s+employee|Transfer\s+From|"
            r"Transfer\s+Amount)",
            re.I,
        )
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()
            error_match = self.SALARY_PAYMENT_ERROR_PATTERN.search(body_text)
            form_ready = self._find_select_employee_field_optional(
                timeout=1
            ) and self._find_salary_transfer_from_field_optional(timeout=1)

            if error_match and not screen_pattern.search(body_text):
                raise AssertionError(
                    "Pay Employee screen showed a salary payment error: "
                    f"{error_match.group(0)}\n\nPage text:\n{body_text}"
                )

            if screen_pattern.search(body_text) and form_ready:
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for Pay Employee screen after clicking Pay Employee.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _select_employee(self, employee_name: str):
        employee_field = self._find_select_employee_field()
        self._select_dropdown_option(
            employee_field,
            employee_name,
            "Select employee dropdown",
            option_text=employee_name,
            choose_first_filtered=True,
            allow_keyboard_fallback=True,
        )
        self._assert_value_visible(employee_name, "selected employee")

    def _select_salary_transfer_from_account(self, from_account: str):
        account_field = self._find_salary_transfer_from_field()
        self._select_dropdown_option(
            account_field,
            from_account,
            "Transfer From dropdown",
            option_text=from_account,
            choose_first_filtered=False,
            allow_keyboard_fallback=False,
        )
        self._assert_value_visible(from_account, "selected Transfer From account")

    def _find_select_employee_field(self):
        field = self._find_select_employee_field_optional(timeout=30)

        if field:
            return field

        raise AssertionError(
            "Could not find Select employee field.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _find_select_employee_field_optional(self, timeout: float = 1):
        label = re.compile(r"Select\s+employee", re.I)

        return self._find_visible_field_optional(
            [
                lambda frame: frame.get_by_label(label),
                lambda frame: frame.get_by_placeholder(label),
                lambda frame: frame.get_by_role("combobox", name=label),
                lambda frame: frame.get_by_role("textbox", name=label),
                lambda frame: frame.locator(
                    'input[aria-label*="Select employee" i], '
                    'input[placeholder*="Select employee" i], '
                    'input[aria-label*="employee" i], '
                    'input[placeholder*="employee" i], '
                    'input[id*="employee" i], input[name*="employee" i], '
                    'input[id*="emp" i], input[name*="emp" i], '
                    '[role="combobox"][aria-label*="employee" i]'
                ),
                lambda frame: self._nearby_field_candidate(frame, label),
            ],
            timeout=timeout,
        )

    def _find_salary_transfer_from_field(self):
        field = self._find_salary_transfer_from_field_optional(timeout=30)

        if field:
            return field

        raise AssertionError(
            "Could not find Transfer From field.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _find_salary_transfer_from_field_optional(self, timeout: float = 1):
        label = re.compile(r"Transfer\s+From", re.I)

        return self._find_visible_field_optional(
            [
                lambda frame: frame.get_by_label(label),
                lambda frame: frame.get_by_placeholder(label),
                lambda frame: frame.get_by_role("combobox", name=label),
                lambda frame: frame.get_by_role("textbox", name=label),
                lambda frame: frame.locator(
                    'input[aria-label*="Transfer From" i], '
                    'input[placeholder*="Transfer From" i], '
                    'input[id*="from" i], input[name*="from" i], '
                    'account-input input, manage-accounts input, '
                    '[role="combobox"][aria-label*="Transfer From" i]'
                ),
                lambda frame: self._nearby_field_candidate(frame, label),
            ],
            timeout=timeout,
        )

    def _find_employee_search_field_optional(self):
        search_pattern = re.compile(r"(Search\s+Employees?|Employee)", re.I)

        for frame in self.page.frames:
            search = self._visible_enabled_first(
                [
                    frame.locator("input[placeholder*='Search Employee' i]"),
                    frame.locator("input[aria-label*='Search Employee' i]"),
                    frame.locator("input[id*='employee' i][id*='search' i]"),
                    frame.locator("input[name*='employee' i][name*='search' i]"),
                    frame.locator("search-box input"),
                    frame.locator("payment-search-box input"),
                    frame.locator(".search-box input"),
                    frame.locator(".payment-search-box-container input"),
                    frame.get_by_role("searchbox"),
                    frame.get_by_role("textbox", name=search_pattern),
                    frame.get_by_placeholder(search_pattern),
                    frame.locator("input[type='search']"),
                    frame.locator("input[aria-label*='search' i]"),
                    frame.locator("input[placeholder*='search' i]"),
                    frame.locator("input[id*='search' i]"),
                    frame.locator("input[name*='search' i]"),
                ]
            )

            if search:
                return search

        return None

    def _wait_for_transaction_summary_screen(self, timeout: float = 45):
        summary_pattern = re.compile(
            r"(Transaction\s+Summary|Review\s+Transaction|Review\s+Details|Summary)",
            re.I,
        )
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()
            error_match = self.SALARY_PAYMENT_ERROR_PATTERN.search(body_text)

            if error_match and not summary_pattern.search(body_text):
                raise AssertionError(
                    "Salary payment failed before Transaction Summary screen: "
                    f"{error_match.group(0)}\n\nPage text:\n{body_text}"
                )

            if summary_pattern.search(body_text):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for Transaction Summary screen after clicking "
            f"Proceed.\n{self._page_snapshot()}"
        )

    def _missing_transaction_summary_values(self, salary_data, summary_text):
        expected_value_groups = [
            ("Transfer From",),
            (salary_data["fromAccount"],),
            ("Transfer Amount", "Amount"),
            tuple(self._amount_review_variants(salary_data["amount"])),
        ]

        if salary_data.get("remarks"):
            expected_value_groups.extend(
                [
                    ("Remarks", "Remark"),
                    (salary_data["remarks"],),
                ]
            )

        return [
            values
            for values in expected_value_groups
            if not any(
                self._normalize_text(value) in summary_text for value in values if value
            )
        ]

    def _employee_details_present(self):
        label_pattern = re.compile(r"(Employee\s+Details|Select\s+employee)", re.I)

        for frame in self.page.frames:
            labels = frame.locator("label, span, div, td, th, oj-label").filter(
                has_text=label_pattern
            )

            try:
                label_count = labels.count()
            except Exception:
                continue

            for index in range(label_count):
                label = labels.nth(index)

                try:
                    if not label.is_visible(timeout=300):
                        continue
                except Exception:
                    continue

                for xpath in (
                    "xpath=ancestor::tr[1]",
                    "xpath=ancestor::*[contains(concat(' ', normalize-space(@class), ' '), ' row ')][1]",
                    "xpath=ancestor::*[contains(concat(' ', normalize-space(@class), ' '), ' oj-flex ')][1]",
                    "xpath=ancestor::*[self::div][2]",
                ):
                    try:
                        scope_text = label.locator(xpath).inner_text(timeout=300)
                    except Exception:
                        continue

                    if self._has_employee_detail_value(scope_text):
                        return True

        body_text = self._normalized_body_text()
        return bool(
            re.search(r"employee\s+details\s+[a-z0-9]", body_text, re.I)
            or re.search(r"select\s+employee\s+[a-z0-9]", body_text, re.I)
        )

    def _has_employee_detail_value(self, text: str):
        normalized = self._normalize_text(text)

        if not normalized:
            return False

        value_text = re.sub(
            r"(employee\s+details|select\s+employee|:|-)",
            " ",
            normalized,
            flags=re.I,
        ).strip()

        return bool(re.search(r"[a-z0-9]", value_text, re.I))

    def _wait_for_salary_payment_final_confirmation_or_fail(
        self,
        success_text,
        timeout: float = 45,
    ):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()
            error_match = self.SALARY_PAYMENT_ERROR_PATTERN.search(body_text)

            if error_match and not success_text.search(body_text):
                raise AssertionError(
                    "Salary payment failed before final confirmation screen: "
                    f"{error_match.group(0)}\n\nPage text:\n{body_text}"
                )

            if success_text.search(body_text):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for salary payment successful confirmation.\n"
            f"{self._page_snapshot()}"
        )

    def _salary_payment_success_visible(self, timeout: float = 5):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if self.SALARY_PAYMENT_SUCCESS_PATTERN.search(self._normalized_body_text()):
                return True

            self.page.wait_for_timeout(500)

        return False

    def _record_locators(self, frame):
        return [
            frame.locator("tbody tr"),
            frame.locator(".oj-table-body-row"),
            frame.locator("[role='row']"),
            frame.locator(".oj-listview-item"),
            frame.locator(".oj-listview-item-element"),
            frame.locator("oj-list-item-layout"),
            frame.locator("li"),
            frame.locator("[data-oj-context]"),
            frame.locator("div[class*='employee' i]"),
            frame.locator("div[class*='salary' i]"),
            frame.locator("div[class*='list' i]"),
            frame.locator("div[class*='card' i]"),
        ]

    def _employee_snapshot(self) -> str:
        rows = []
        script = """
        els => els.map((e, idx) => ({
          idx,
          tag: e.tagName.toLowerCase(),
          id: e.id || "",
          role: e.getAttribute("role") || "",
          classes: e.className || "",
          text: (e.innerText || e.textContent || "").trim().replace(/\\s+/g, " "),
          visible: !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length)
        }))
        """
        selector = (
            "tbody tr, .oj-table-body-row, [role='row'], .oj-listview-item, "
            ".oj-listview-item-element, oj-list-item-layout, li, "
            "[data-oj-context], div[class*='employee' i], "
            "div[class*='salary' i], div[class*='list' i], div[class*='card' i]"
        )

        for frame_index, frame in enumerate(self.page.frames):
            try:
                records = frame.locator(selector).evaluate_all(script)
            except Exception as exc:
                rows.append(f"frame={frame_index} url={frame.url} unavailable: {exc}")
                continue

            for record in records:
                rows.append(
                    "frame={frame} url={url} idx={idx} tag={tag} id={id} "
                    "role={role} classes={classes} visible={visible} text={text}".format(
                        frame=frame_index,
                        url=frame.url,
                        **record,
                    )
                )

        return "\n".join(rows) or "No employee record candidates were found."

    def _save_debug_artifacts(self) -> Path:
        artifact_dir = (
            Path("artifacts")
            / f"pay_salary_internal_bene_{time.strftime('%Y%m%d_%H%M%S')}"
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
                    "EMPLOYEES",
                    self._employee_snapshot(),
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
