import re
import time
from pathlib import Path

from pageObjects.neftRegPayeeOnetime import NeftRegPayeeOnetimePage


class OpenRegularFdPayInterestAutoRenewNoNomineePage(NeftRegPayeeOnetimePage):
    FD_ERROR_PATTERN = re.compile(
        r"(unable\s+to\s+process|failed|error|invalid|required|please\s+select|"
        r"please\s+enter|not\s+available|insufficient)",
        re.I,
    )
    OPEN_FIXED_DEPOSIT_PATTERN = re.compile(
        r"^\s*Open\s+Fixed\s+Deposit\s*$",
        re.I,
    )
    CONFIRM_AND_PROCEED_PATTERN = re.compile(
        r"^\s*Confirm\s*(?:and|&)\s*Proceed\s*$",
        re.I,
    )

    def open_regular_fd_pay_interest_auto_renew_no_nominee(self, deposit_data):
        try:
            self._handle_post_login_popups()
            self.navigate_to_open_fixed_deposit()
            self.enter_source_account_details(deposit_data)
            self.enter_deposit_details(deposit_data)
            self.enter_tenure_details(deposit_data)
            self.select_nominee_details(deposit_data)
            self.verify_review_details(deposit_data)
            self.accept_terms_and_submit()
            self.confirm_otp_if_required(deposit_data.get("otp"))
            self.assert_fixed_deposit_booked_successfully()
        except Exception as exc:
            artifact_dir = self._save_debug_artifacts()
            error_message = str(exc)
            if not isinstance(exc, AssertionError):
                error_message = f"{type(exc).__name__}: {exc}"

            raise AssertionError(
                f"{error_message}\n\nDebug artifacts saved to: {artifact_dir.resolve()}"
            ) from None

    def navigate_to_open_fixed_deposit(self):
        self._hover_menu_item("Accounts")
        self._hover_menu_item("Deposits")
        self._click_open_fixed_deposit()
        self._wait_for_open_fixed_deposit_screen(timeout=45)

    def enter_source_account_details(self, deposit_data):
        self._select_radio_or_card_option(
            deposit_data["depositType"],
            "Deposit Type",
        )
        self._select_account_dropdown(
            self._find_select_account_field,
            deposit_data["sourceAccount"],
            "Select Account dropdown",
        )
        self._assert_yes_bank_branch_present()
        self._click_action(
            re.compile(r"^\s*Proceed\s*$", re.I),
            "Proceed button on Open Fixed Deposit screen",
            value_fragments=("Proceed",),
            timeout=30,
        )
        self._wait_for_deposit_details_section(timeout=45)

    def enter_deposit_details(self, deposit_data):
        amount = self._find_deposit_amount_field()
        self._type_like_user(amount, deposit_data["depositAmount"], verify_value=False)

        self._select_radio_or_card_option(deposit_data["interest"], "Interest")
        self._select_dropdown_by_label(
            self._find_interest_payout_field,
            deposit_data["interestPayout"],
            "Interest payout dropdown",
        )
        self._select_account_dropdown(
            self._find_choose_payment_option_field,
            deposit_data["choosePaymentOption"],
            "Choose payment option dropdown",
        )
        self._select_dropdown_by_label(
            self._find_principal_field,
            deposit_data["principal"],
            "Principal dropdown",
        )

        if not self._select_tenure_section_visible():
            self._click_action(
                re.compile(r"^\s*Proceed\s*$", re.I),
                "Proceed button on Deposit details section",
                value_fragments=("Proceed",),
                timeout=30,
            )

        self._wait_for_select_tenure_section(timeout=45)

    def enter_tenure_details(self, deposit_data):
        self._reset_open_popup()
        tenure_values = (
            ("years", "Years"),
            ("months", "Months"),
            ("days", "Days"),
        )

        for key, label in tenure_values:
            field = self._find_tenure_field(label)
            self._type_like_user(field, deposit_data[key], verify_value=False)

        self._click_action(
            re.compile(r"^\s*SHOW\s+RESULTS\s*$", re.I),
            "SHOW RESULTS button",
            value_fragments=("SHOW", "RESULTS"),
            timeout=30,
        )
        self._wait_for_continue_with_tenure(timeout=60)
        self._click_action(
            re.compile(r".*CONTINUE\s+WITH\s+TENURE\s+OF.*", re.I),
            "CONTINUE WITH TENURE OF button",
            value_fragments=("CONTINUE", "TENURE"),
            timeout=30,
        )
        self._wait_for_select_nominee_section(timeout=45)

    def select_nominee_details(self, deposit_data):
        self._select_radio_or_card_option(
            deposit_data["nomineeType"],
            "Select Nominee type",
        )
        self._click_action(
            re.compile(r"^\s*NEXT\s*$", re.I),
            "NEXT button on Select Nominee section",
            value_fragments=("NEXT",),
            timeout=30,
        )
        self._wait_for_review_details_screen(timeout=45)

    def verify_review_details(self, deposit_data):
        deadline = time.monotonic() + 30
        review_text = ""
        missing_values = []

        while time.monotonic() < deadline:
            review_text = self._normalized_body_text()
            missing_values = self._missing_review_values(deposit_data, review_text)

            if not missing_values:
                return

            self.page.wait_for_timeout(500)

        review_text = self._normalized_body_text()
        missing_values = self._missing_review_values(deposit_data, review_text)

        if missing_values:
            raise AssertionError(
                "Review Details page is missing expected fixed deposit value(s): "
                f"{missing_values}\n\nReview text:\n{review_text}"
            )

    def accept_terms_and_submit(self):
        self._select_terms_and_conditions_checkbox()
        self._click_action(
            re.compile(r"^\s*Proceed\s*$", re.I),
            "Proceed button on Review Details screen",
            value_fragments=("Proceed",),
            timeout=30,
        )

    def confirm_otp_if_required(self, otp: str | None):
        if self._fixed_deposit_success_visible(timeout=5):
            return

        if not otp:
            return

        try:
            self._find_otp_fields(len(otp), timeout=8)
        except AssertionError:
            if self._fixed_deposit_success_visible(timeout=8):
                return
            return

        self._fill_otp(otp)
        self._click_action(
            self.CONFIRM_AND_PROCEED_PATTERN,
            "Confirm and Proceed button on OTP popup",
            value_fragments=("Confirm", "Proceed"),
            timeout=30,
        )

    def assert_fixed_deposit_booked_successfully(self):
        deadline = time.monotonic() + 60

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()
            error_match = self.FD_ERROR_PATTERN.search(body_text)

            if error_match and not self._fixed_deposit_success_text_present(body_text):
                raise AssertionError(
                    "Fixed Deposit booking failed before final confirmation: "
                    f"{error_match.group(0)}\n\nPage text:\n{body_text}"
                )

            if self._fixed_deposit_success_text_present(body_text):
                self._assert_action_visible(
                    re.compile(r"^\s*Go\s+to\s+Home\s*$", re.I),
                    "Go to Home option",
                    value_fragments=("Go", "Home"),
                )
                self._assert_action_visible(
                    re.compile(r"^\s*FD\s+Advice\s*$", re.I),
                    "FD Advice option",
                    value_fragments=("FD", "Advice"),
                )
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for Fixed Deposit booked successfully confirmation.\n"
            f"{self._page_snapshot()}"
        )

    def _click_open_fixed_deposit(self, timeout: float = 30):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                menu_item = self._visible_enabled_first(
                    [
                        frame.get_by_role(
                            "menuitem",
                            name=self.OPEN_FIXED_DEPOSIT_PATTERN,
                        ),
                        frame.get_by_role(
                            "link",
                            name=self.OPEN_FIXED_DEPOSIT_PATTERN,
                        ),
                        frame.locator("span").filter(
                            has_text=self.OPEN_FIXED_DEPOSIT_PATTERN
                        ),
                        frame.locator("div.text-css1").filter(
                            has_text=self.OPEN_FIXED_DEPOSIT_PATTERN
                        ),
                        frame.locator("div").filter(
                            has_text=self.OPEN_FIXED_DEPOSIT_PATTERN
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
            "Could not find Open Fixed Deposit submenu item.\n"
            f"{self._page_snapshot()}\n\n{self._action_snapshot()}"
        )

    def _wait_for_open_fixed_deposit_screen(self, timeout: float = 45):
        self._wait_for_body_text(
            re.compile(r"Open\s+Fixed\s+Deposit|Deposit\s+Type|Select\s+Account", re.I),
            "Open Fixed Deposit screen",
            timeout=timeout,
        )

    def _wait_for_deposit_details_section(self, timeout: float = 45):
        self._wait_for_body_text(
            re.compile(r"Deposit\s+details|Deposit\s+Amount|Interest\s+Payout", re.I),
            "Deposit details section",
            timeout=timeout,
        )

    def _wait_for_select_tenure_section(self, timeout: float = 45):
        self._wait_for_body_text(
            re.compile(r"Select\s+tenure|Years|Months|Days|SHOW\s+RESULTS", re.I),
            "Select tenure section",
            timeout=timeout,
        )

    def _select_tenure_section_visible(self):
        return bool(
            re.search(
                r"Select\s+tenure|SHOW\s+RESULTS",
                self._normalized_body_text(),
                re.I,
            )
        )

    def _wait_for_continue_with_tenure(self, timeout: float = 60):
        self._wait_for_body_text(
            re.compile(r"CONTINUE\s+WITH\s+TENURE\s+OF", re.I),
            "CONTINUE WITH TENURE OF result",
            timeout=timeout,
        )

    def _wait_for_select_nominee_section(self, timeout: float = 45):
        self._wait_for_body_text(
            re.compile(r"Select\s+Nominee|Nominee\s+type|No\s+Nominee", re.I),
            "Select Nominee section",
            timeout=timeout,
        )

    def _wait_for_review_details_screen(self, timeout: float = 45):
        self._wait_for_body_text(
            re.compile(r"Review\s+Details|Review\s+Transaction", re.I),
            "Review Details screen",
            timeout=timeout,
        )

    def _wait_for_body_text(self, pattern, description: str, timeout: float = 45):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()
            error_match = self.FD_ERROR_PATTERN.search(body_text)

            if error_match and not pattern.search(body_text):
                raise AssertionError(
                    f"{description} showed an error: {error_match.group(0)}"
                    f"\n\nPage text:\n{body_text}"
                )

            if pattern.search(body_text):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            f"Timed out waiting for {description}.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _select_radio_or_card_option(self, value: str, description: str):
        try:
            self._select_radio_option(value, description)
            self._assert_any_value_visible((value,), f"selected {description}")
            return
        except AssertionError:
            pass

        option_pattern = re.compile(rf"^\s*{re.escape(value)}\s*$", re.I)
        option = self._find_visible_field(
            [
                lambda frame: frame.get_by_label(option_pattern),
                lambda frame: frame.get_by_role("button", name=option_pattern),
                lambda frame: frame.get_by_role("radio", name=option_pattern),
                lambda frame: frame.locator("label").filter(has_text=option_pattern),
                lambda frame: frame.locator("span").filter(has_text=option_pattern),
                lambda frame: frame.locator("div").filter(has_text=option_pattern),
            ],
            f"{description} option {value}",
            timeout=15,
            enabled_only=False,
        )

        try:
            option.click(timeout=10000)
        except Exception:
            option.evaluate("element => element.click()")

        self.page.wait_for_timeout(500)
        self._assert_any_value_visible((value,), f"selected {description}")

    def _select_dropdown_by_label(self, field_factory, value: str, description: str):
        field = field_factory()
        self._select_dropdown_option(
            field,
            value,
            description,
            option_text=value,
            choose_first_filtered=False,
            allow_keyboard_fallback=True,
        )
        self._reset_open_popup()

    def _select_account_dropdown(self, field_factory, account_number: str, description: str):
        field = field_factory()
        self._select_dropdown_option(
            field,
            account_number,
            description,
            option_text=account_number,
            choose_first_filtered=False,
            allow_keyboard_fallback=False,
        )
        self._assert_any_value_visible((account_number,), f"selected {description}")

    def _reset_open_popup(self):
        for key in ("Escape", "Tab"):
            try:
                self.page.keyboard.press(key)
                self.page.wait_for_timeout(300)
            except Exception:
                pass

    def _find_select_account_field(self):
        return self._find_dropdown_field(
            re.compile(r"Select\s+Account|Source\s+Account|Account", re.I),
            "Select Account field",
            extra_selector=(
                'input[aria-label*="Select Account" i], '
                'input[placeholder*="Select Account" i], '
                'input[id*="account" i], input[name*="account" i], '
                'account-input input, manage-accounts input, '
                '[role="combobox"][aria-label*="Account" i]'
            ),
        )

    def _find_deposit_amount_field(self):
        return self._find_text_field(
            re.compile(r"Deposit\s+Amount|Amount", re.I),
            "Deposit amount field",
            extra_selector=(
                'input[aria-label*="Deposit Amount" i], '
                'input[placeholder*="Deposit Amount" i], '
                'input[id*="amount" i], input[name*="amount" i], '
                'input[inputmode="decimal"], input[type="number"]'
            ),
        )

    def _find_interest_payout_field(self):
        return self._find_dropdown_field(
            re.compile(r"Interest\s+Payout", re.I),
            "Interest payout field",
            extra_selector=(
                'input[aria-label*="Interest Payout" i], '
                'input[placeholder*="Interest Payout" i], '
                'input[id*="payout" i], input[name*="payout" i], '
                '[role="combobox"][aria-label*="Interest Payout" i], '
                'oj-select-single[aria-label*="Interest Payout" i]'
            ),
        )

    def _find_choose_payment_option_field(self):
        return self._find_dropdown_field(
            re.compile(r"Choose\s+Payment\s+Option|Payment\s+Option", re.I),
            "Choose payment option field",
            extra_selector=(
                'input[aria-label*="Payment Option" i], '
                'input[placeholder*="Payment Option" i], '
                'input[id*="payment" i], input[name*="payment" i], '
                'account-input input, manage-accounts input, '
                '[role="combobox"][aria-label*="Payment Option" i]'
            ),
        )

    def _find_principal_field(self):
        return self._find_dropdown_field(
            re.compile(r"Principal", re.I),
            "Principal field",
            extra_selector=(
                'input[aria-label*="Principal" i], '
                'input[placeholder*="Principal" i], '
                'input[id*="principal" i], input[name*="principal" i], '
                '[role="combobox"][aria-label*="Principal" i], '
                'oj-select-single[aria-label*="Principal" i]'
            ),
        )

    def _find_tenure_field(self, label_text: str):
        label = re.compile(rf"^{re.escape(label_text)}$", re.I)
        selector_name = label_text[:-1].lower()

        return self._find_text_field(
            label,
            f"{label_text} tenure field",
            extra_selector=(
                f'input[aria-label*="{label_text}" i], '
                f'input[placeholder*="{label_text}" i], '
                f'input[id*="{selector_name}" i], '
                f'input[name*="{selector_name}" i]'
            ),
        )

    def _find_text_field(self, label, description: str, extra_selector: str):
        return self._find_visible_field(
            [
                lambda frame: frame.get_by_label(label),
                lambda frame: frame.get_by_placeholder(label),
                lambda frame: frame.get_by_role("textbox", name=label),
                lambda frame: frame.locator(extra_selector),
                lambda frame: self._nearby_field_candidate(frame, label),
            ],
            description,
        )

    def _find_dropdown_field(self, label, description: str, extra_selector: str):
        return self._find_visible_field(
            [
                lambda frame: frame.get_by_label(label),
                lambda frame: frame.get_by_placeholder(label),
                lambda frame: frame.get_by_role("combobox", name=label),
                lambda frame: frame.get_by_role("textbox", name=label),
                lambda frame: frame.locator(extra_selector),
                lambda frame: self._nearby_field_candidate(frame, label),
            ],
            description,
        )

    def _assert_yes_bank_branch_present(self):
        field = self._find_yes_bank_branch_field_optional(timeout=10)
        branch_value = ""

        if field:
            try:
                branch_value = field.input_value(timeout=1000).strip()
            except Exception:
                try:
                    branch_value = field.inner_text(timeout=1000).strip()
                except Exception:
                    branch_value = ""

        if not branch_value:
            branch_value = self._nearby_value_after_label(
                re.compile(r"YES\s*BANK\s*branch", re.I),
                timeout=5,
            )

        if not branch_value:
            branch_value = self._visible_yes_bank_branch_text()

        if not branch_value:
            raise AssertionError(
                "YES BANK branch field did not show a value after selecting "
                "the source account.\n"
                f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
            )

    def _find_yes_bank_branch_field_optional(self, timeout: float = 1):
        label = re.compile(r"YES\s*BANK\s*branch", re.I)

        return self._find_visible_field_optional(
            [
                lambda frame: frame.get_by_label(label),
                lambda frame: frame.get_by_placeholder(label),
                lambda frame: frame.get_by_role("textbox", name=label),
                lambda frame: frame.locator(
                    'input[aria-label*="YES BANK branch" i], '
                    'input[placeholder*="YES BANK branch" i], '
                    'input[id*="branch" i], input[name*="branch" i]'
                ),
                lambda frame: self._nearby_field_candidate(frame, label),
            ],
            timeout=timeout,
            enabled_only=False,
        )

    def _nearby_value_after_label(self, label_pattern, timeout: float = 5):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                labels = frame.locator("label, span, div, oj-label").filter(
                    has_text=label_pattern
                )

                try:
                    count = labels.count()
                except Exception:
                    continue

                for index in range(min(count, 8)):
                    label = labels.nth(index)

                    try:
                        label_text = self._normalize_text(label.inner_text(timeout=300))
                    except Exception:
                        continue

                    if not label_pattern.search(label_text) or len(label_text) > 80:
                        continue

                    value = self._visible_text_near_label(label, label_text)

                    if value:
                        return value

            self.page.wait_for_timeout(500)

        return ""

    def _visible_text_near_label(self, label, normalized_label_text: str):
        try:
            value = label.evaluate(
                """
                element => {
                  const normalize = text => (text || "").replace(/\\s+/g, " ").trim();
                  const visible = node => {
                    if (!node) return false;
                    const style = window.getComputedStyle(node);
                    return !!(node.offsetWidth || node.offsetHeight || node.getClientRects().length)
                      && style.display !== "none"
                      && style.visibility !== "hidden";
                  };
                  const container = element.closest(
                    ".oj-flex, .oj-form-control, .form-field, .row, li, tr, div"
                  ) || element.parentElement || element;
                  const fields = container.querySelectorAll(
                    "input:not([type='hidden']), textarea, [role='combobox']"
                  );

                  for (const field of fields) {
                    if (!visible(field)) continue;
                    const value = normalize(field.value || field.innerText || field.textContent);
                    if (value) return value;
                  }

                  let sibling = element.nextElementSibling;
                  for (let index = 0; sibling && index < 6; index += 1) {
                    if (visible(sibling)) {
                      const value = normalize(sibling.value || sibling.innerText || sibling.textContent);
                      if (value) return value;
                    }
                    sibling = sibling.nextElementSibling;
                  }

                  return "";
                }
                """
            )
        except Exception:
            return ""

        normalized_value = self._normalize_text(value)

        if not normalized_value or normalized_value == normalized_label_text:
            return ""

        return str(value).strip()

    def _visible_yes_bank_branch_text(self):
        body_text = self._normalized_body_text()
        match = re.search(
            r"yes\s+bank\s+branch\s+(.+?)(?:\s+change|\s+disclaimer|\s+proceed|$)",
            body_text,
            re.I,
        )

        if not match:
            return ""

        value = match.group(1).strip()

        if not value or self._normalize_text(value) == "yes bank branch":
            return ""

        return value

    def _select_terms_and_conditions_checkbox(self):
        checkbox = self._find_terms_checkbox(timeout=15)

        try:
            checkbox.check(timeout=5000)
            return
        except Exception:
            pass

        try:
            checkbox.click(timeout=5000)
        except Exception:
            checkbox.evaluate("element => element.click()")

        self.page.wait_for_timeout(500)

    def _find_terms_checkbox(self, timeout: float = 15):
        terms_pattern = re.compile(r"(I\s+accept|Terms\s*&?\s*Conditions|Terms)", re.I)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                checkbox = self._visible_enabled_first(
                    [
                        frame.get_by_role("checkbox", name=terms_pattern),
                        frame.locator(
                            'input[type="checkbox"][aria-label*="Terms" i], '
                            'input[type="checkbox"][id*="terms" i], '
                            'input[type="checkbox"][name*="terms" i]'
                        ),
                    ]
                )

                if checkbox:
                    return checkbox

                scopes = [
                    frame.locator("label").filter(has_text=terms_pattern),
                    frame.locator("oj-checkboxset").filter(has_text=terms_pattern),
                    frame.locator("span").filter(has_text=terms_pattern),
                    frame.locator("div").filter(has_text=terms_pattern),
                ]

                for scope in scopes:
                    checkbox = self._find_checkbox_in_scope(scope)

                    if checkbox:
                        return checkbox

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Could not find I accept the Terms & Conditions checkbox.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _find_checkbox_in_scope(self, scope):
        try:
            count = min(scope.count(), 6)
        except Exception:
            return None

        for index in range(count):
            candidate_scope = scope.nth(index)
            checkbox = self._visible_enabled_first(
                [
                    candidate_scope.locator('input[type="checkbox"]'),
                    candidate_scope.locator('[role="checkbox"]'),
                    candidate_scope.locator("label"),
                ]
            )

            if checkbox:
                return checkbox

        return None

    def _missing_review_values(self, deposit_data, review_text):
        expected_value_groups = [
            ("Review Details", "Review Transaction"),
            (deposit_data["depositType"],),
            (deposit_data["sourceAccount"],),
            tuple(self._amount_review_variants(deposit_data["depositAmount"])),
        ]

        tenure_variants = self._tenure_review_variants(deposit_data)
        if tenure_variants:
            expected_value_groups.append(tuple(tenure_variants))

        optional_review_fields = [
            (
                r"\bInterest\b|Interest\s+Option",
                (deposit_data["interest"],),
            ),
            (
                r"Interest\s+Payout|Payout",
                (deposit_data["interestPayout"],),
            ),
            (
                r"Choose\s+Payment\s+Option|Payment\s+Option",
                (deposit_data["choosePaymentOption"],),
            ),
            (
                r"\bPrincipal\b|Renew",
                (deposit_data["principal"],),
            ),
            (
                r"Nominee|Nominee\s+type",
                (deposit_data["nomineeType"],),
            ),
        ]

        for label_pattern, values in optional_review_fields:
            if re.search(label_pattern, review_text, re.I) and any(
                self._normalize_text(value) in review_text for value in values if value
            ):
                expected_value_groups.append(values)

        return [
            values
            for values in expected_value_groups
            if not any(
                self._normalize_text(value) in review_text for value in values if value
            )
        ]

    def _amount_review_variants(self, amount: str):
        variants = list(super()._amount_review_variants(amount))

        if self._is_number(amount):
            amount_value = float(amount)
            amount_with_decimal = f"{amount_value:.2f}"
            amount_without_decimal = (
                str(int(amount_value))
                if amount_value.is_integer()
                else str(amount_value)
            )
            variants.extend(
                [
                    f"INR {self._format_indian_grouped_number(amount_with_decimal)}",
                    self._format_indian_grouped_number(amount_with_decimal),
                    f"INR {self._format_indian_grouped_number(amount_without_decimal)}",
                    self._format_indian_grouped_number(amount_without_decimal),
                ]
            )

        return list(dict.fromkeys(value for value in variants if value))

    def _tenure_review_variants(self, deposit_data):
        years = deposit_data.get("years", "")
        months = deposit_data.get("months", "")
        days = deposit_data.get("days", "")
        values = [
            f"{years} Years {months} Months {days} Days",
            f"{years} Year {months} Month {days} Day",
            f"{years}Y {months}M {days}D",
        ]

        if years:
            values.append(f"{years} Years")

        return list(dict.fromkeys(value for value in values if value))

    def _fixed_deposit_success_visible(self, timeout: float = 5):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if self._fixed_deposit_success_text_present(self._normalized_body_text()):
                return True

            self.page.wait_for_timeout(500)

        return False

    @staticmethod
    def _fixed_deposit_success_text_present(body_text: str):
        return bool(
            re.search(r"Fixed\s+Deposit\s+of", body_text, re.I)
            and re.search(r"Has\s+been\s+booked\s+successfully", body_text, re.I)
        )

    def _assert_action_visible(self, pattern, description: str, value_fragments=()):
        action = self._find_action_optional(
            pattern,
            value_fragments=value_fragments,
            timeout=10,
        )

        if action:
            return

        raise AssertionError(
            f"Could not find clickable {description} on final confirmation screen.\n"
            f"{self._page_snapshot()}\n\n{self._action_snapshot()}"
        )

    def _find_action_optional(self, label_pattern, value_fragments=(), timeout=1):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                action = self._visible_enabled_first(
                    [
                        frame.get_by_role("button", name=label_pattern),
                        frame.get_by_role("link", name=label_pattern),
                        frame.locator("button").filter(has_text=label_pattern),
                        frame.locator("oj-button").filter(has_text=label_pattern),
                        frame.locator("[role='button']").filter(has_text=label_pattern),
                        frame.locator("a").filter(has_text=label_pattern),
                        *self._input_value_locators(frame, value_fragments),
                    ]
                )

                if action:
                    return action

            self.page.wait_for_timeout(200)

        return None

    @staticmethod
    def _format_indian_grouped_number(value: str):
        integer_part, separator, decimal_part = value.partition(".")
        sign = ""

        if integer_part.startswith("-"):
            sign = "-"
            integer_part = integer_part[1:]

        if len(integer_part) <= 3:
            grouped_integer = integer_part
        else:
            grouped_integer = integer_part[-3:]
            remaining = integer_part[:-3]

            while remaining:
                grouped_integer = f"{remaining[-2:]},{grouped_integer}"
                remaining = remaining[:-2]

        grouped_value = f"{sign}{grouped_integer}"

        if separator:
            grouped_value = f"{grouped_value}.{decimal_part}"

        return grouped_value

    def _save_debug_artifacts(self) -> Path:
        artifact_dir = (
            Path("artifacts")
            / f"open_regular_fd_pay_interest_auto_renew_no_nominee_{time.strftime('%Y%m%d_%H%M%S')}"
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
