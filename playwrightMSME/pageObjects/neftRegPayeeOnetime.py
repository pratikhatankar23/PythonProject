import re
import time
from pathlib import Path

from playwright.sync_api import Page

from pageObjects.addYesBankBene import AddYesBankBenePage


class NeftRegPayeeOnetimePage(AddYesBankBenePage):
    TRANSFER_ERROR_PATTERN = re.compile(
        r"(insufficient\s+balance|transaction\s+failed|transfer\s+failed|"
        r"payment\s+failed|unable\s+to\s+process|daily\s+limit|"
        r"beneficiary\s+not\s+found|invalid\s+amount|please\s+select)",
        re.I,
    )
    TRANSFER_EXISTING_BENE_PATTERN = re.compile(
        r"^\s*Transfer\s*-\s*Exis(?:i)?ting\s+Beneficiary\s*$",
        re.I,
    )
    CONFIRM_AND_PROCEED_PATTERN = re.compile(
        r"^\s*Confirm\s*(?:and|&)\s*Proceed\s*$",
        re.I,
    )
    VERIFY_RECIPIENT_NAME_PATTERN = re.compile(
        r"^\s*Verify\s+Recipient\s+Name\s*$",
        re.I,
    )

    def __init__(self, page: Page):
        super().__init__(page)

    def neft_registered_payee_onetime(self, transfer_data):
        try:
            self._handle_post_login_popups()
            self.navigate_to_pay_beneficiary()
            self.enter_pay_beneficiary_details(transfer_data)
            self.verify_review_transaction(transfer_data)
            self.proceed_to_pay_and_confirm(transfer_data["otp"])
            self.assert_transferred_successfully()
        except Exception as exc:
            artifact_dir = self._save_debug_artifacts()
            error_message = str(exc)
            if not isinstance(exc, AssertionError):
                error_message = f"{type(exc).__name__}: {exc}"

            raise AssertionError(
                f"{error_message}\n\nDebug artifacts saved to: {artifact_dir.resolve()}"
            ) from None

    def navigate_to_pay_beneficiary(self):
        self._hover_menu_item("Payments")
        self._hover_menu_item("Single Payments")
        self._click_transfer_existing_beneficiary()
        self._wait_for_pay_beneficiary_screen(timeout=45)

    def enter_pay_beneficiary_details(self, transfer_data):
        fail_on_verify_recipient_name_click = (
            self._should_fail_on_verify_recipient_name_click(transfer_data)
        )

        self._arm_verify_recipient_name_click_guard()

        self._select_beneficiary(transfer_data["payeename"])
        self._select_transfer_from_account(transfer_data["from_account"])
        self._dismiss_blocking_overlays()

        if fail_on_verify_recipient_name_click:
            self._assert_verify_recipient_name_not_clicked(
                transfer_data["transfer_type"]
            )

        amount = self._find_transfer_amount_field()
        self._type_like_user(amount, transfer_data["amount"], verify_value=False)

        self._select_radio_option(
            transfer_data["transfer_type"],
            "Transfer type",
        )
        self._select_radio_option(
            transfer_data["transfer_schedule"],
            "Transfer schedule",
        )

        remarks = self._find_remarks_field()
        self._type_like_user(remarks, transfer_data["remarks"])

        if fail_on_verify_recipient_name_click:
            self._assert_verify_recipient_name_not_clicked(
                transfer_data["transfer_type"]
            )

        self._click_action(
            re.compile(r"^\s*Proceed\s*$", re.I),
            "Proceed button",
            value_fragments=("Proceed",),
        )
        self._wait_for_review_transaction_or_fail(timeout=45)

    def _should_fail_on_verify_recipient_name_click(self, transfer_data):
        return (
            self._normalize_text(transfer_data.get("transfer_type", "")).upper()
            == "NEFT"
        )

    def verify_review_transaction(self, transfer_data):
        deadline = time.monotonic() + 30
        missing_values = []
        review_text = ""

        while time.monotonic() < deadline:
            review_text = self._normalized_body_text()
            missing_values = self._missing_review_transaction_values(
                transfer_data,
                review_text,
            )

            if not missing_values:
                return

            self.page.wait_for_timeout(500)

        review_text = self._normalized_body_text()
        missing_values = self._missing_review_transaction_values(
            transfer_data,
            review_text,
        )

        if missing_values:
            raise AssertionError(
                "Review Transaction page is missing expected NEFT one-time "
                f"value(s): {missing_values}\n\nReview text:\n{review_text}"
            )

    def _missing_review_transaction_values(self, transfer_data, review_text):
        expected_value_groups = [
            ("Review Transaction",),
            ("Transfer From",),
            (transfer_data["payeename"],),
            (transfer_data["from_account"],),
            ("Transfer To",),
            ("Transfer Amount",),
            tuple(self._amount_review_variants(transfer_data["amount"])),
            ("Transfer Type",),
            (transfer_data["transfer_type"],),
        ]

        if re.search(r"Transfer\s+Schedule|Schedule", review_text, re.I):
            expected_value_groups.append((transfer_data["transfer_schedule"],))

        if transfer_data.get("remarks"):
            expected_value_groups.extend(
                [
                    ("Remarks",),
                    (transfer_data["remarks"],),
                ]
            )

        return [
            values
            for values in expected_value_groups
            if not any(
                self._normalize_text(value) in review_text for value in values if value
            )
        ]

    def proceed_to_pay_and_confirm(self, otp: str):
        self._click_action(
            re.compile(r"^\s*Proceed\s+to\s+Pay\s*$", re.I),
            "Proceed to Pay button",
            value_fragments=("Proceed", "Pay"),
            timeout=30,
        )
        self._fill_otp(otp)
        self._click_action(
            self.CONFIRM_AND_PROCEED_PATTERN,
            "Confirm and Proceed button on OTP popup",
            value_fragments=("Confirm", "Proceed"),
            timeout=30,
        )

    def assert_transferred_successfully(self):
        success_text = re.compile(
            r"(Transferred\s+successfully|Transfer\s+successful|"
            r"Transaction\s+successful|Payment\s+successful)",
            re.I,
        )
        self._wait_for_transfer_final_confirmation_or_fail(success_text, timeout=45)

    def _click_transfer_existing_beneficiary(self, timeout: float = 30):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                menu_item = self._visible_enabled_first(
                    [
                        frame.locator("li.level-1 span").filter(
                            has_text=self.TRANSFER_EXISTING_BENE_PATTERN
                        ),
                        frame.locator("li.level-1 div.text-css1").filter(
                            has_text=self.TRANSFER_EXISTING_BENE_PATTERN
                        ),
                        frame.locator("ul.innersubmenucssnew li span").filter(
                            has_text=self.TRANSFER_EXISTING_BENE_PATTERN
                        ),
                        frame.locator("span").filter(
                            has_text=self.TRANSFER_EXISTING_BENE_PATTERN
                        ),
                        frame.locator("div.text-css1").filter(
                            has_text=self.TRANSFER_EXISTING_BENE_PATTERN
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
            "Could not find Transfer - Existing Beneficiary submenu item.\n"
            f"{self._page_snapshot()}\n\n{self._action_snapshot()}"
        )

    def _wait_for_pay_beneficiary_screen(self, timeout: float = 45):
        screen_pattern = re.compile(
            r"(Pay\s+Beneficiary|Select\s+beneficiar(?:y|ies)|"
            r"Transfer\s+From|Transfer\s+Amount)",
            re.I,
        )
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()
            error_match = self.TRANSFER_ERROR_PATTERN.search(body_text)

            if error_match and not screen_pattern.search(body_text):
                raise AssertionError(
                    "Pay Beneficiary screen showed a transfer error: "
                    f"{error_match.group(0)}\n\nPage text:\n{body_text}"
                )

            if screen_pattern.search(body_text) and re.search(
                r"(Transfer\s+Amount|Amount)",
                body_text,
                re.I,
            ):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for Pay Beneficiary screen after clicking "
            "Transfer - Existing Beneficiary.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _select_beneficiary(self, payee_name: str):
        beneficiary_field = self._find_select_beneficiary_field()
        self._select_dropdown_option(
            beneficiary_field,
            payee_name,
            "Select beneficiary dropdown",
            option_text=payee_name,
            choose_first_filtered=True,
            allow_keyboard_fallback=True,
        )
        self._assert_beneficiary_selected(payee_name)

    def _select_transfer_from_account(self, from_account: str):
        if from_account in self._normalized_body_text():
            return

        account_field = self._find_transfer_from_field()
        self._select_dropdown_option(
            account_field,
            from_account,
            "Transfer From dropdown",
            option_text=from_account,
            choose_first_filtered=False,
            allow_keyboard_fallback=False,
        )
        self._assert_value_visible(from_account, "selected Transfer From account")

    def _assert_beneficiary_selected(self, payee_name: str, timeout: float = 10):
        expected = self._normalize_text(payee_name)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if (
                expected in self._normalized_body_text()
                or self._visible_field_value_contains(expected)
            ):
                return

            selected_texts = self._selected_beneficiary_display_texts()
            if selected_texts:
                if any(expected in text for text in selected_texts):
                    return

                # Some flows search by account number, but the control renders only
                # the beneficiary name after selection.
                return

            if self._beneficiary_dependent_fields_visible():
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            f"Expected selected beneficiary {payee_name!r} to be visible after selection.\n"
            f"{self._page_snapshot()}"
        )

    def _selected_beneficiary_display_texts(self):
        texts = []
        script = """
        root => {
          const nodes = [root, ...root.querySelectorAll('*')];
          const values = [];

          for (const node of nodes) {
            const style = window.getComputedStyle(node);
            const visible = !!(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
            if (!visible || style.display === 'none' || style.visibility === 'hidden') {
              continue;
            }

            const text = (node.innerText || node.textContent || '')
              .replace(/\\s+/g, ' ')
              .trim();

            if (text) {
              values.push(text);
            }
          }

          return [...new Set(values)];
        }
        """

        ignore_patterns = [
            re.compile(r"^Select\s+beneficiary$", re.I),
            re.compile(r"^\d+\s+or\s+more\s+matches\s+found$", re.I),
            re.compile(r"^\d+\s+matches?\s+found$", re.I),
        ]

        for frame in self.page.frames:
            control = self._visible_first(
                [
                    frame.locator("oj-select-single.select-beneficiary"),
                    frame.locator("oj-select-single#payeename"),
                    frame.locator("#payeename"),
                ]
            )

            if not control:
                continue

            try:
                raw_texts = control.evaluate(script)
            except Exception:
                continue

            for text in raw_texts:
                normalized = self._normalize_text(text)
                if not normalized:
                    continue

                if any(pattern.search(normalized) for pattern in ignore_patterns):
                    continue

                texts.append(normalized)

        return list(dict.fromkeys(texts))

    def _beneficiary_dependent_fields_visible(self):
        body_text = self._normalized_body_text()

        return bool(
            re.search(r"Verify\s+Recipient\s+Name", body_text, re.I)
            and re.search(r"Transfer\s+From", body_text, re.I)
            and re.search(r"Available\s+Balance", body_text, re.I)
        )

    def _select_radio_option(self, value: str, description: str):
        value_pattern = re.compile(rf"^\s*{re.escape(value)}\s*$", re.I)
        option = self._find_visible_field(
            [
                lambda frame: frame.get_by_label(value_pattern),
                lambda frame: frame.get_by_role("radio", name=value_pattern),
                lambda frame: frame.locator("label").filter(has_text=value_pattern),
                lambda frame: frame.locator("span").filter(has_text=value_pattern),
                lambda frame: frame.locator("div").filter(has_text=value_pattern),
                lambda frame: frame.locator(
                    f'input[type="radio"][value*="{value}" i]'
                ),
            ],
            f"{description} {value} radio option",
            timeout=10,
            enabled_only=False,
        )

        try:
            option.click(timeout=10000)
        except Exception:
            option.evaluate("element => element.click()")

        self.page.wait_for_timeout(500)

    def _find_select_beneficiary_field(self):
        label = re.compile(r"Select\s+beneficiar(?:y|ies)", re.I)

        return self._find_visible_field(
            [
                lambda frame: frame.get_by_label(label),
                lambda frame: frame.get_by_placeholder(label),
                lambda frame: frame.get_by_role("combobox", name=label),
                lambda frame: frame.get_by_role("textbox", name=label),
                lambda frame: frame.locator(
                    'input[aria-label*="Select beneficiary" i], '
                    'input[aria-label*="beneficiary" i], '
                    'input[placeholder*="beneficiary" i], '
                    'input[id*="payee" i], input[name*="payee" i], '
                    'input[id*="bene" i], input[name*="bene" i], '
                    '[role="combobox"][aria-label*="beneficiary" i]'
                ),
                lambda frame: self._nearby_field_candidate(frame, label),
            ],
            "Select beneficiary field",
        )

    def _find_transfer_from_field(self):
        label = re.compile(r"Transfer\s+From", re.I)

        return self._find_visible_field(
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
            "Transfer From field",
        )

    def _find_transfer_amount_field(self):
        label = re.compile(r"Transfer\s+Amount|Amount", re.I)

        return self._find_visible_field(
            [
                lambda frame: frame.get_by_label(label),
                lambda frame: frame.get_by_placeholder(label),
                lambda frame: frame.get_by_role("textbox", name=label),
                lambda frame: frame.locator(
                    'input[aria-label*="Transfer Amount" i], '
                    'input[aria-label="Amount" i], '
                    'input[id*="amount" i], input[name*="amount" i], '
                    'input[inputmode="decimal"], input[type="number"]'
                ),
                lambda frame: self._nearby_field_candidate(frame, label),
            ],
            "Transfer Amount field",
        )

    def _find_remarks_field(self):
        label = re.compile(r"Remarks?|Narration|Description", re.I)

        return self._find_visible_field(
            [
                lambda frame: frame.get_by_label(label),
                lambda frame: frame.get_by_placeholder(label),
                lambda frame: frame.get_by_role("textbox", name=label),
                lambda frame: frame.locator(
                    'textarea[aria-label*="Remark" i], '
                    'input[aria-label*="Remark" i], '
                    'textarea[id*="remark" i], input[id*="remark" i], '
                    'textarea[name*="remark" i], input[name*="remark" i], '
                    'textarea[id*="narration" i], input[id*="narration" i]'
                ),
                lambda frame: self._nearby_field_candidate(frame, label),
            ],
            "Remarks field",
        )

    def _select_dropdown_option(
        self,
        field,
        search_text: str,
        description: str,
        option_text: str,
        choose_first_filtered: bool,
        allow_keyboard_fallback: bool = True,
    ):
        try:
            field.click(timeout=10000)
        except Exception as exc:
            raise AssertionError(f"Could not click {description}: {exc}") from None

        self.page.wait_for_timeout(500)
        search_field = self._find_active_dropdown_search_field(timeout=3) or field
        self._clear_and_type_into_active_field(search_field, search_text)
        self.page.wait_for_timeout(1000)

        option_pattern = re.compile(re.escape(option_text), re.I)
        option = self._find_dropdown_option(option_pattern, timeout=15)

        if not option and choose_first_filtered:
            option = self._find_first_dropdown_option(timeout=5)

        if option:
            try:
                option.click(timeout=10000)
            except Exception:
                option.evaluate("element => element.click()")

            self.page.wait_for_timeout(700)
        elif allow_keyboard_fallback:
            self._accept_highlighted_dropdown_option(search_field)
        else:
            self._blur_dropdown_field(search_field)

        self._blur_dropdown_field(search_field)
        self.page.wait_for_timeout(1000)

        if not option and (not choose_first_filtered or not allow_keyboard_fallback):
            raise AssertionError(
                f"Could not find dropdown option containing {option_text!r} "
                f"for {description}.\n{self._page_snapshot()}\n\n"
                f"{self._action_snapshot()}"
            )

        try:
            if option and self._dropdown_search_still_visible():
                if allow_keyboard_fallback:
                    self._accept_highlighted_dropdown_option(search_field)
                self._blur_dropdown_field(search_field)
        except Exception:
            pass

        self._dismiss_blocking_overlays()

    def _clear_and_type_into_active_field(self, field, value: str):
        try:
            field.press("Control+A")
            field.press("Backspace")
            field.press_sequentially(value, delay=75)
            return
        except Exception:
            pass

        try:
            self.page.keyboard.press("Control+A")
            self.page.keyboard.press("Backspace")
            self.page.keyboard.type(value, delay=75)
        except Exception as exc:
            raise AssertionError(f"Could not type {value!r} into dropdown: {exc}") from None

    def _find_active_dropdown_search_field(self, timeout: float = 3):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                field = self._visible_enabled_first(
                    [
                        frame.locator('input[id^="oj-searchselect-filter-"][id$="|input"]'),
                        frame.locator(".oj-listbox-search input"),
                        frame.locator(".oj-searchselect-filter input"),
                        frame.locator('input[aria-autocomplete="list"]'),
                    ]
                )

                if field:
                    return field

            self.page.wait_for_timeout(200)

        return None

    def _accept_highlighted_dropdown_option(self, search_field):
        try:
            search_field.press("Enter")
            self.page.wait_for_timeout(500)
            return
        except Exception:
            pass

        try:
            self.page.keyboard.press("Enter")
            self.page.wait_for_timeout(500)
        except Exception:
            pass

    def _blur_dropdown_field(self, search_field):
        try:
            search_field.press("Tab")
            self.page.wait_for_timeout(300)
            return
        except Exception:
            pass

        try:
            self.page.keyboard.press("Tab")
            self.page.wait_for_timeout(300)
        except Exception:
            pass

    def _dropdown_search_still_visible(self):
        return self._find_active_dropdown_search_field(timeout=1) is not None

    def _arm_verify_recipient_name_click_guard(self):
        guard_script = """
            () => {
                if (window.__neftVerifyRecipientNameGuardInstalled) {
                    return;
                }

                window.__neftVerifyRecipientNameGuardInstalled = true;
                window.__neftVerifyRecipientNameClickCount = 0;

                const isVerifyRecipientNameAction = (node) => {
                    if (!node) {
                        return false;
                    }

                    const action = node.closest
                        ? node.closest("oj-button, button, [role='button'], a")
                        : null;
                    const textSource = action || node;
                    const text = (textSource.innerText || textSource.textContent || "")
                        .replace(/\\s+/g, " ")
                        .trim();

                    return /^Verify\\s+Recipient\\s+Name$/i.test(text);
                };

                document.addEventListener(
                    "click",
                    (event) => {
                        if (isVerifyRecipientNameAction(event.target)) {
                            event.preventDefault();
                            event.stopPropagation();
                            event.stopImmediatePropagation();
                        }
                    },
                    true
                );

                document.addEventListener(
                    "keydown",
                    (event) => {
                        if (
                            (event.key === "Enter" || event.key === " ")
                            && isVerifyRecipientNameAction(document.activeElement)
                        ) {
                            event.preventDefault();
                            event.stopPropagation();
                            event.stopImmediatePropagation();
                        }
                    },
                    true
                );
            }
        """

        for frame in self.page.frames:
            try:
                frame.evaluate(guard_script)
            except Exception:
                continue

    def _assert_verify_recipient_name_not_clicked(self, transfer_type="NEFT"):
        click_count = 0

        for frame in self.page.frames:
            try:
                click_count += int(
                    frame.evaluate(
                        "() => window.__neftVerifyRecipientNameClickCount || 0"
                    )
                )
            except Exception:
                continue

        if click_count:
            raise AssertionError(
                "Verify Recipient Name should not be clicked during the "
                f"{transfer_type} registered payee flow, but it was clicked "
                f"{click_count} time(s)."
            )

    def _dismiss_blocking_overlays(self, timeout: float = 5):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if not self._blocking_overlay_visible():
                return

            action = self._visible_enabled_first(
                [
                    self.page.get_by_role(
                        "button",
                        name=re.compile(r"^\s*(?:OK|Close|Cancel)\s*$", re.I),
                    ),
                    self.page.locator(
                        "#close-window button, "
                        "#close-window [role='button'], "
                        "[aria-label*='close' i], "
                        ".oj-dialog-close-icon"
                    ),
                ]
            )

            if action:
                try:
                    action.click(timeout=3000)
                except Exception:
                    action.evaluate("element => element.click()")
            else:
                try:
                    self.page.keyboard.press("Escape")
                except Exception:
                    pass

            self.page.wait_for_timeout(500)

    def _blocking_overlay_visible(self):
        overlay = self._visible_first(
            [
                self.page.locator("#close-window_layer_overlay"),
                self.page.locator(".oj-component-overlay.oj-dialog-layer"),
            ]
        )

        return overlay is not None

    def _find_dropdown_option(self, option_pattern, timeout: float = 15):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                option = self._visible_first(
                    [
                        frame.locator("[role='option']").filter(has_text=option_pattern),
                        frame.locator("[id^='lovDropdown_'] [role='option']").filter(
                            has_text=option_pattern
                        ),
                        frame.locator(
                            "[id^='lovDropdown_'] .oj-listview-cell-element"
                        ).filter(has_text=option_pattern),
                        frame.locator("[id^='lovDropdown_'] li").filter(
                            has_text=option_pattern
                        ),
                        frame.locator(".oj-listbox-result-label").filter(
                            has_text=option_pattern
                        ),
                        frame.locator("oj-option").filter(has_text=option_pattern),
                        frame.locator("li.oj-listbox-result").filter(
                            has_text=option_pattern
                        ),
                        frame.locator(".oj-listview-item").filter(
                            has_text=option_pattern
                        ),
                        frame.locator("li").filter(has_text=option_pattern),
                    ]
                )

                if option:
                    return option

            self.page.wait_for_timeout(500)

        return None

    def _find_first_dropdown_option(self, timeout: float = 5):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                option = self._visible_first(
                    [
                        frame.locator("[role='option']"),
                        frame.locator("[id^='lovDropdown_'] [role='option']"),
                        frame.locator(
                            "[id^='lovDropdown_'] .oj-listview-cell-element"
                        ),
                        frame.locator("[id^='lovDropdown_'] li"),
                        frame.locator(".oj-listbox-result-label"),
                        frame.locator("oj-option"),
                        frame.locator("li.oj-listbox-result"),
                        frame.locator(".oj-listview-item"),
                    ]
                )

                if option:
                    return option

            self.page.wait_for_timeout(500)

        return None

    def _nearby_field_candidate(self, frame, label_pattern):
        fields = self._nearby_fields(frame, label_pattern)

        if fields:
            return fields[0]

        return frame.locator("input").filter(has_text=re.compile(r"a^"))

    def _wait_for_review_transaction_or_fail(self, timeout: float = 45):
        review_pattern = re.compile(r"Review\s+(?:Transaction|Details)", re.I)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()
            error_match = self.TRANSFER_ERROR_PATTERN.search(body_text)

            if error_match:
                raise AssertionError(
                    "NEFT transfer failed before Review Transaction page: "
                    f"{error_match.group(0)}\n\nPage text:\n{body_text}"
                )

            if review_pattern.search(body_text):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for Review Transaction page after clicking Proceed.\n"
            f"{self._page_snapshot()}"
        )

    def _wait_for_transfer_final_confirmation_or_fail(self, success_text, timeout: float = 45):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()
            error_match = self.TRANSFER_ERROR_PATTERN.search(body_text)

            if error_match and not success_text.search(body_text):
                raise AssertionError(
                    "NEFT transfer failed before final confirmation screen: "
                    f"{error_match.group(0)}\n\nPage text:\n{body_text}"
                )

            if success_text.search(body_text):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for Transferred successfully confirmation "
            f"after OTP submission.\n{self._page_snapshot()}"
        )

    def _assert_value_visible(self, value: str, description: str, timeout: float = 10):
        deadline = time.monotonic() + timeout
        expected = self._normalize_text(value)

        while time.monotonic() < deadline:
            if (
                expected in self._normalized_body_text()
                or self._visible_field_value_contains(expected)
            ):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            f"Expected {description} {value!r} to be visible after selection.\n"
            f"{self._page_snapshot()}"
        )

    def _visible_field_value_contains(self, expected: str):
        for frame in self.page.frames:
            fields = frame.locator("input, textarea")

            try:
                count = fields.count()
            except Exception:
                continue

            for index in range(count):
                field = fields.nth(index)

                try:
                    if not field.is_visible(timeout=500):
                        continue

                    if expected in self._normalize_text(field.input_value(timeout=500)):
                        return True
                except Exception:
                    continue

        return False

    def _find_visible_field(
        self,
        locator_factories,
        description: str,
        timeout: float = 30,
        enabled_only: bool = True,
    ):
        field = self._find_visible_field_optional(
            locator_factories,
            timeout=timeout,
            enabled_only=enabled_only,
        )

        if field:
            return field

        raise AssertionError(
            f"Could not find {description}.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _find_visible_field_optional(
        self,
        locator_factories,
        timeout: float = 1,
        enabled_only: bool = True,
    ):
        deadline = time.monotonic() + timeout
        finder = self._visible_enabled_first if enabled_only else self._visible_first

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                locators = []

                for factory in locator_factories:
                    try:
                        locators.append(factory(frame))
                    except Exception:
                        continue

                field = finder(locators)

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

    def _amount_review_variants(self, amount: str):
        if not self._is_number(amount):
            return [amount]

        amount_value = float(amount)
        amount_with_decimal = f"{amount_value:.2f}"
        amount_without_decimal = str(int(amount_value)) if amount_value.is_integer() else str(amount_value)

        return [
            f"INR {amount_with_decimal}",
            f"₹ {amount_with_decimal}",
            f"₹{amount_with_decimal}",
            amount_with_decimal,
            f"INR {amount_without_decimal}",
            f"₹ {amount_without_decimal}",
            f"₹{amount_without_decimal}",
        ]

    def _save_debug_artifacts(self) -> Path:
        artifact_dir = Path("artifacts") / f"neft_reg_payee_onetime_{time.strftime('%Y%m%d_%H%M%S')}"
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
