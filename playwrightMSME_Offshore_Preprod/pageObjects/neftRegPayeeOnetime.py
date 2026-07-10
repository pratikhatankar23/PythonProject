import re
import time
from datetime import date
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
        self._select_transfer_when_if_required(transfer_data)

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
            expected_value_groups.append(
                tuple(self._schedule_review_variants(transfer_data["transfer_schedule"]))
            )

        if transfer_data.get("transfer_when"):
            expected_value_groups.extend(
                [
                    ("Transfer When", "Transfer Date", "Transfer On"),
                    tuple(self._transfer_when_review_variants(transfer_data)),
                ]
            )

        if transfer_data.get("transfer_time") and re.search(
            r"Transfer\s+Time|Payment\s+Time|Execution\s+Time",
            review_text,
            re.I,
        ):
            expected_value_groups.extend(
                [
                    ("Transfer Time",),
                    tuple(self._transfer_time_review_variants(transfer_data)),
                ]
            )

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
            r"Transaction\s+successful|Payment\s+successful|"
            r"Transfer\s+has\s+been\s+scheduled\s+successfully|"
            r"scheduled\s+successfully)",
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

    def _select_transfer_when_if_required(self, transfer_data):
        transfer_when = transfer_data.get("transfer_when")

        if not transfer_when:
            return

        requested_date = None
        if self._normalize_text(transfer_when) != "today":
            requested_date = self._parse_transfer_when_date(transfer_when)

        self._wait_for_transfer_when_field(timeout=30)
        transfer_when_field = self._find_transfer_when_field()
        self._click_transfer_when_calendar_icon(transfer_when_field)

        if requested_date:
            selected_dates = self._click_calendar_date(requested_date)
        else:
            selected_dates = self._click_first_enabled_calendar_date()

        try:
            transfer_when_field.press("Tab")
        except Exception:
            pass

        field_value = self._transfer_when_field_value(transfer_when_field)
        selected_values = [field_value, *selected_dates, transfer_when]
        selected_values = list(dict.fromkeys(value for value in selected_values if value))
        transfer_data["_selected_transfer_when"] = selected_values[0]
        transfer_data["_selected_transfer_when_variants"] = selected_values
        self._select_transfer_time_for_dated_transfer(transfer_data, requested_date)

    def _select_transfer_time_for_dated_transfer(self, transfer_data, requested_date):
        if not requested_date:
            return

        transfer_time = transfer_data.get("transfer_time")

        if not transfer_time:
            if getattr(self, "REQUIRE_TRANSFER_TIME_FOR_DATED_TRANSFER", False):
                raise AssertionError(
                    "transfer_time is required in test data for dated "
                    "pay later transactions."
                )

            return

        if getattr(self, "ALLOW_MISSING_TRANSFER_TIME_FIELD", False):
            transfer_time_field = self._find_transfer_time_field_optional(timeout=5)

            if not transfer_time_field:
                return
        else:
            self._wait_for_transfer_time_field(timeout=30)
            transfer_time_field = self._find_transfer_time_field()

        self._select_dropdown_option(
            transfer_time_field,
            transfer_time,
            "Transfer Time dropdown",
            option_text=transfer_time,
            choose_first_filtered=False,
            allow_keyboard_fallback=True,
        )
        self._assert_any_value_visible(
            self._transfer_time_review_variants(transfer_data),
            "selected Transfer Time",
        )

    def _parse_transfer_when_date(self, transfer_when):
        raw_value = str(transfer_when or "").strip()

        text_match = re.fullmatch(
            r"(\d{1,2})[-/\s]([A-Za-z]{3,})[-/,\s]+(\d{4})",
            raw_value,
        )
        if text_match:
            day, month, year = text_match.groups()
            month_number = self._month_number(month)
            if month_number:
                return self._build_transfer_when_date(
                    int(year),
                    int(month_number),
                    int(day),
                    raw_value,
                )

        iso_match = re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", raw_value)
        if iso_match:
            year, month, day = iso_match.groups()
            return self._build_transfer_when_date(
                int(year),
                int(month),
                int(day),
                raw_value,
            )

        numeric_match = re.fullmatch(
            r"(\d{1,2})[-/\s](\d{1,2})[-/\s](\d{4})",
            raw_value,
        )
        if numeric_match:
            day, month, year = numeric_match.groups()
            return self._build_transfer_when_date(
                int(year),
                int(month),
                int(day),
                raw_value,
            )

        raise AssertionError(
            "Unsupported transfer_when value "
            f"{transfer_when!r}. Use 'Today' or a date like '30-Jun-2026', "
            "'30/06/2026', or '2026-06-30'."
        )

    @staticmethod
    def _build_transfer_when_date(year, month, day, raw_value):
        try:
            return date(year, month, day)
        except ValueError as exc:
            raise AssertionError(
                f"Invalid transfer_when date {raw_value!r}: {exc}"
            ) from None

    def _wait_for_transfer_when_field(self, timeout: float = 30):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()
            error_match = self.TRANSFER_ERROR_PATTERN.search(body_text)

            if error_match and not re.search(r"Transfer\s+When|Transfer\s+Date", body_text, re.I):
                raise AssertionError(
                    "Transfer When field failed to load after selecting Transfer "
                    f"Schedule: {error_match.group(0)}\n\nPage text:\n{body_text}"
                )

            if self._find_transfer_when_field_optional(timeout=1):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for Transfer When field after selecting Transfer "
            f"Schedule.\n{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _find_transfer_when_field(self):
        field = self._find_transfer_when_field_optional(timeout=30)

        if field:
            return field

        raise AssertionError(
            "Could not find Transfer When field.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _find_transfer_when_field_optional(self, timeout: float = 1):
        label = re.compile(r"Transfer\s+When|Transfer\s+Date|Transfer\s+On", re.I)

        return self._find_visible_field_optional(
            [
                lambda frame: frame.get_by_label(label),
                lambda frame: frame.get_by_placeholder(label),
                lambda frame: frame.get_by_role("textbox", name=label),
                lambda frame: frame.locator(
                    'input[aria-label*="Transfer When" i], '
                    'input[placeholder*="Transfer When" i], '
                    'input[aria-label*="Transfer Date" i], '
                    'input[placeholder*="Transfer Date" i], '
                    'input[id*="transfer" i][id*="when" i], '
                    'input[name*="transfer" i][name*="when" i], '
                    'input[id*="transfer" i][id*="date" i], '
                    'input[name*="transfer" i][name*="date" i], '
                    'oj-input-date input, oj-date-picker input, '
                    'input[class*="date" i]'
                ),
                lambda frame: self._nearby_field_candidate(frame, label),
            ],
            timeout=timeout,
        )

    def _wait_for_transfer_time_field(self, timeout: float = 30):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()
            error_match = self.TRANSFER_ERROR_PATTERN.search(body_text)

            if error_match and not re.search(
                r"Transfer\s+Time|Payment\s+Time|Execution\s+Time",
                body_text,
                re.I,
            ):
                raise AssertionError(
                    "Transfer Time field failed to load after selecting Transfer "
                    f"When: {error_match.group(0)}\n\nPage text:\n{body_text}"
                )

            if self._find_transfer_time_field_optional(timeout=1):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for Transfer Time field after selecting Transfer "
            f"When.\n{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _find_transfer_time_field(self):
        field = self._find_transfer_time_field_optional(timeout=30)

        if field:
            return field

        raise AssertionError(
            "Could not find Transfer Time field.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _find_transfer_time_field_optional(self, timeout: float = 1):
        label = re.compile(
            r"(?:Select\s+)?Transfer\s+Time|Payment\s+Time|Execution\s+Time",
            re.I,
        )

        return self._find_visible_field_optional(
            [
                lambda frame: frame.get_by_label(label),
                lambda frame: frame.get_by_placeholder(label),
                lambda frame: frame.get_by_role("combobox", name=label),
                lambda frame: frame.get_by_role("textbox", name=label),
                lambda frame: frame.locator(
                    'input[aria-label*="Transfer Time" i], '
                    'input[placeholder*="Transfer Time" i], '
                    'input[id*="transfer" i][id*="time" i], '
                    'input[name*="transfer" i][name*="time" i], '
                    '[role="combobox"][aria-label*="Transfer Time" i], '
                    '[role="combobox"][id*="transfer" i][id*="time" i], '
                    'oj-select-single[aria-label*="Transfer Time" i], '
                    'oj-select-one[aria-label*="Transfer Time" i], '
                    'oj-select-single[id*="transfer" i][id*="time" i], '
                    'oj-select-one[id*="transfer" i][id*="time" i]'
                ),
                lambda frame: self._nearby_field_candidate(frame, label),
            ],
            timeout=timeout,
        )

    def _click_transfer_when_calendar_icon(self, transfer_when_field):
        calendar_action = self._find_calendar_action_near_field(transfer_when_field)

        if calendar_action:
            try:
                calendar_action.click(timeout=10000, force=True)
                self.page.wait_for_timeout(500)
                return
            except Exception:
                try:
                    calendar_action.evaluate("element => element.click()")
                    self.page.wait_for_timeout(500)
                    return
                except Exception:
                    pass

        try:
            transfer_when_field.click(timeout=10000)
            self.page.wait_for_timeout(500)
            return
        except Exception as exc:
            raise AssertionError(
                f"Could not open Transfer When calendar: {exc}\n"
                f"{self._page_snapshot()}\n\n{self._action_snapshot()}"
            ) from None

    def _find_calendar_action_near_field(self, field):
        scopes = []

        for xpath in (
            "xpath=ancestor::oj-input-date[1]",
            "xpath=ancestor::*[contains(translate(@class, "
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'date')][1]",
            "xpath=ancestor::*[self::div or self::oj-form-layout][1]",
            "xpath=ancestor::*[self::div or self::oj-form-layout][2]",
            "xpath=ancestor::*[self::div or self::oj-form-layout][3]",
        ):
            try:
                scopes.append(field.locator(xpath))
            except Exception:
                continue

        scopes.append(self.page.locator("body"))

        calendar_pattern = re.compile(r"(calendar|date|picker|select)", re.I)

        for scope in scopes:
            action = self._visible_enabled_first(
                [
                    scope.get_by_role("button", name=calendar_pattern),
                    scope.get_by_role("link", name=calendar_pattern),
                    scope.locator("[aria-label*='calendar' i]"),
                    scope.locator("[title*='calendar' i]"),
                    scope.locator("[aria-label*='date' i]"),
                    scope.locator("[title*='date' i]"),
                    scope.locator(".oj-inputdatetime-calendar-icon"),
                    scope.locator(".oj-datepicker-trigger"),
                    scope.locator("[class*='calendar' i]"),
                    scope.locator("[class*='date-picker' i]"),
                ]
            )

            if action:
                return action

        return None

    def _click_first_enabled_calendar_date(self, timeout: float = 15):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                date_action = self._first_enabled_calendar_date_in_frame(frame)

                if not date_action:
                    continue

                selected_dates = self._calendar_date_values(date_action)

                try:
                    date_action.click(timeout=10000, force=True)
                except Exception:
                    date_action.evaluate("element => element.click()")

                self.page.wait_for_timeout(700)
                return selected_dates

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Could not find an enabled date in the Transfer When calendar.\n"
            f"{self._page_snapshot()}\n\n{self._action_snapshot()}"
        )

    def _click_calendar_date(self, requested_date: date, timeout: float = 20):
        deadline = time.monotonic() + timeout
        last_calendar_month = None

        while time.monotonic() < deadline:
            calendar_month = self._visible_calendar_month_year()

            if calendar_month:
                last_calendar_month = calendar_month
                month_delta = (
                    (requested_date.year - calendar_month[0]) * 12
                    + requested_date.month
                    - calendar_month[1]
                )

                if month_delta:
                    if self._click_calendar_month_navigation(month_delta):
                        self.page.wait_for_timeout(500)
                        continue

                    break

            for frame in self.page.frames:
                date_action = self._enabled_calendar_date_in_frame(
                    frame,
                    requested_date.day,
                )

                if not date_action:
                    continue

                selected_dates = self._calendar_date_values(date_action)

                try:
                    date_action.click(timeout=10000, force=True)
                except Exception:
                    date_action.evaluate("element => element.click()")

                self.page.wait_for_timeout(700)
                selected_dates.extend(self._date_variants_from_date(requested_date))
                return list(dict.fromkeys(value for value in selected_dates if value))

            self.page.wait_for_timeout(500)

        expected_date = requested_date.strftime("%d-%b-%Y")
        month_text = ""

        if last_calendar_month:
            month_text = (
                f" Calendar was showing "
                f"{self._month_name(last_calendar_month[1])} {last_calendar_month[0]}."
            )

        raise AssertionError(
            f"Could not select enabled Transfer When date {expected_date}."
            f"{month_text}\n{self._page_snapshot()}\n\n{self._action_snapshot()}"
        )

    def _enabled_calendar_date_in_frame(self, frame, day: int):
        day_pattern = re.compile(rf"^\s*{day}\s*$")
        locators = [
            frame.locator(
                ".oj-datepicker-calendar td:not(.oj-disabled) "
                "a:not(.oj-disabled):not([aria-disabled='true'])"
            ).filter(has_text=day_pattern),
            frame.locator(
                "td:not(.oj-disabled):not([aria-disabled='true']) "
                "a:not(.oj-disabled):not([aria-disabled='true'])"
            ).filter(has_text=day_pattern),
            frame.locator(
                "[role='gridcell']:not([aria-disabled='true']) "
                "a:not([aria-disabled='true'])"
            ).filter(has_text=day_pattern),
            frame.locator(
                "[role='gridcell']:not([aria-disabled='true'])"
            ).filter(has_text=day_pattern),
            frame.locator(
                "button:not([disabled]):not([aria-disabled='true'])"
            ).filter(has_text=day_pattern),
            frame.locator(
                "a:not([aria-disabled='true'])"
            ).filter(has_text=day_pattern),
        ]

        for locator in locators:
            try:
                count = locator.count()
            except Exception:
                continue

            for index in range(count):
                candidate = locator.nth(index)

                if self._is_enabled_calendar_date(candidate):
                    return candidate

        return None

    def _visible_calendar_month_year(self):
        month_year_pattern = re.compile(
            r"\b(January|February|March|April|May|June|July|August|September|"
            r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|"
            r"Oct|Nov|Dec)\s+(\d{4})\b",
            re.I,
        )

        for frame in self.page.frames:
            for locator in (
                frame.locator(
                    ".oj-datepicker-popup, .oj-datepicker, .oj-popup, "
                    "[role='dialog'], [class*='datepicker' i], [id*='datepicker' i]"
                ),
                frame.locator("body"),
            ):
                try:
                    count = min(locator.count(), 3)
                except Exception:
                    continue

                for index in range(count):
                    candidate = locator.nth(index)

                    try:
                        if not candidate.is_visible(timeout=300):
                            continue
                        text = candidate.inner_text(timeout=500)
                    except Exception:
                        continue

                    match = month_year_pattern.search(text)
                    if not match:
                        continue

                    month, year = match.groups()
                    month_number = self._month_number(month)
                    if month_number:
                        return int(year), int(month_number)

        return None

    def _click_calendar_month_navigation(self, month_delta: int):
        nav_pattern = (
            re.compile(r"^\s*(Next|Forward)\s*$", re.I)
            if month_delta > 0
            else re.compile(r"^\s*(Previous|Prev|Back)\s*$", re.I)
        )
        class_fragment = "next" if month_delta > 0 else "prev"

        for frame in self.page.frames:
            action = self._visible_enabled_first(
                [
                    frame.get_by_role("button", name=nav_pattern),
                    frame.get_by_role("link", name=nav_pattern),
                    frame.locator(f".oj-datepicker-{class_fragment}-icon"),
                    frame.locator(
                        f"[aria-label*='{class_fragment}' i], "
                        f"[title*='{class_fragment}' i], "
                        f"[class*='datepicker-{class_fragment}' i]"
                    ),
                ]
            )

            if not action:
                continue

            try:
                action.click(timeout=5000, force=True)
            except Exception:
                action.evaluate("element => element.click()")

            return True

        return False

    def _date_variants_from_date(self, selected_date: date):
        day = selected_date.day
        month = selected_date.month
        year = selected_date.year
        month_number = f"{month:02d}"
        day_number = f"{day:02d}"
        month_name = self._month_name(month)
        month_abbr = month_name[:3]

        return [
            f"{year}-{month_number}-{day_number}",
            f"{year}/{month_number}/{day_number}",
            f"{day_number}/{month_number}/{year}",
            f"{day}/{month}/{year}",
            f"{day_number}-{month_number}-{year}",
            f"{day}-{month}-{year}",
            f"{day}-{month_abbr}-{year}",
            f"{day_number}-{month_abbr}-{year}",
            f"{day} {month_abbr} {year}",
            f"{day} {month_name} {year}",
            f"{day} {month_name}, {year}",
        ]

    def _first_enabled_calendar_date_in_frame(self, frame):
        locators = [
            frame.locator(
                ".oj-datepicker-calendar td:not(.oj-disabled) "
                "a:not(.oj-disabled):not([aria-disabled='true'])"
            ),
            frame.locator(
                "td:not(.oj-disabled):not([aria-disabled='true']) "
                "a:not(.oj-disabled):not([aria-disabled='true'])"
            ),
            frame.locator(
                "[role='gridcell']:not([aria-disabled='true']) "
                "a:not([aria-disabled='true'])"
            ),
            frame.locator(
                "[role='gridcell']:not([aria-disabled='true'])"
            ),
            frame.locator(
                "button:not([disabled]):not([aria-disabled='true'])"
            ).filter(has_text=re.compile(r"^\s*\d{1,2}\s*$")),
            frame.locator(
                "a:not([aria-disabled='true'])"
            ).filter(has_text=re.compile(r"^\s*\d{1,2}\s*$")),
        ]

        for locator in locators:
            try:
                count = locator.count()
            except Exception:
                continue

            for index in range(count):
                candidate = locator.nth(index)

                if self._is_enabled_calendar_date(candidate):
                    return candidate

        return None

    def _is_enabled_calendar_date(self, candidate):
        try:
            if not candidate.is_visible(timeout=300):
                return False
        except Exception:
            return False

        try:
            disabled = candidate.evaluate(
                """
                element => {
                  const node = element.closest("td, [role='gridcell'], button, a") || element;
                  const calendarRoot = element.closest(
                    ".oj-datepicker-calendar, .oj-datepicker-content, "
                    + ".oj-datepicker-popup, .oj-datepicker, .oj-popup, "
                    + "[class*='calendar'], [class*='datepicker'], "
                    + "[id*='calendar'], [id*='datepicker'], [role='dialog']"
                  );
                  const classText = (node.className || "") + " " + (element.className || "");
                  const ariaDisabled = node.getAttribute("aria-disabled") || element.getAttribute("aria-disabled");
                  const disabledAttr = node.hasAttribute("disabled") || element.hasAttribute("disabled");
                  const text = (element.innerText || element.textContent || "").trim();

                  return {
                    inCalendar: !!calendarRoot,
                    disabled: disabledAttr || ariaDisabled === "true" || /disabled|unselectable/i.test(classText),
                    text
                  };
                }
                """
            )
        except Exception:
            return False

        return bool(
            disabled.get("inCalendar")
            and not disabled.get("disabled")
            and re.fullmatch(r"\d{1,2}", str(disabled.get("text") or ""))
        )

    def _calendar_date_values(self, date_action):
        try:
            date_details = date_action.evaluate(
                """
                element => {
                  const popupRoot = element.closest(
                    ".oj-datepicker-popup, .oj-datepicker, .oj-popup, [role='dialog']"
                  );
                  const calendarRoot = popupRoot
                    || element.closest(".oj-datepicker-calendar, [class*='calendar'], [id*='calendar']")
                    || document.body;
                  return {
                    cellText: [
                      element.getAttribute("aria-label") || "",
                      element.getAttribute("title") || "",
                      element.innerText || element.textContent || ""
                    ].join(" ").replace(/\\s+/g, " ").trim(),
                    calendarText: (calendarRoot.innerText || calendarRoot.textContent || "")
                      .replace(/\\s+/g, " ")
                      .trim(),
                    bodyText: (document.body.innerText || document.body.textContent || "")
                      .replace(/\\s+/g, " ")
                      .trim()
                  };
                }
                """
            )
        except Exception:
            return []

        return self._calendar_date_variants(date_details)

    def _calendar_date_variants(self, date_details):
        cell_text = str(date_details.get("cellText") or "").strip()
        calendar_text = str(date_details.get("calendarText") or "").strip()
        body_text = str(date_details.get("bodyText") or "").strip()
        variants = []

        if cell_text:
            variants.append(cell_text)

        day_match = re.search(r"\b(\d{1,2})\b", cell_text)
        month_match = re.search(
            r"\b(January|February|March|April|May|June|July|August|September|"
            r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|"
            r"Oct|Nov|Dec)\s+(\d{4})\b",
            f"{calendar_text} {body_text}",
            re.I,
        )

        if day_match and month_match:
            day = day_match.group(1)
            month_name, year = month_match.groups()
            month_number = self._month_number(month_name)

            if month_number:
                padded_day = day.zfill(2)
                variants.extend(
                    [
                        f"{year}-{month_number}-{padded_day}",
                        f"{padded_day}/{month_number}/{year}",
                        f"{int(day)}/{int(month_number)}/{year}",
                        f"{padded_day}-{month_number}-{year}",
                        f"{int(day)}-{int(month_number)}-{year}",
                        f"{day} {month_name} {year}",
                        f"{day} {month_name}, {year}",
                        f"{day}-{month_name}-{year}",
                    ]
                )

        return list(dict.fromkeys(value for value in variants if value))

    def _transfer_when_field_value(self, field):
        try:
            return field.input_value(timeout=1000).strip()
        except Exception:
            return ""

    def _transfer_when_review_variants(self, transfer_data):
        values = [transfer_data.get("transfer_when", "")]
        selected_value = transfer_data.get("_selected_transfer_when")
        selected_variants = transfer_data.get("_selected_transfer_when_variants", [])

        if selected_variants:
            values.extend(selected_variants)

        if selected_value:
            values.append(selected_value)
            values.extend(self._date_review_variants(selected_value))

        return list(dict.fromkeys(value for value in values if value))

    def _transfer_time_review_variants(self, transfer_data):
        transfer_time = transfer_data.get("transfer_time", "")
        values = [transfer_time]

        if self._normalize_text(transfer_time) == "anytime":
            values.append("Any Time")

        return list(dict.fromkeys(value for value in values if value))

    def _schedule_review_variants(self, schedule_value: str):
        compact_value = re.sub(r"\s+", "", schedule_value or "")
        variants = [schedule_value, compact_value]

        if self._normalize_text(schedule_value) == "one time":
            variants.extend(["oneTime", "onetime", "one-time"])

        return list(dict.fromkeys(value for value in variants if value))

    def _date_review_variants(self, date_value: str):
        variants = {date_value}

        numeric_match = re.fullmatch(
            r"\s*(\d{1,2})[-/\s](\d{1,2})[-/\s](\d{4})\s*",
            date_value,
        )
        if numeric_match:
            first, second, year = numeric_match.groups()
            variants.update(
                {
                    f"{first.zfill(2)}/{second.zfill(2)}/{year}",
                    f"{first.zfill(2)}-{second.zfill(2)}-{year}",
                    f"{int(first)}/{int(second)}/{year}",
                    f"{int(first)}-{int(second)}-{year}",
                }
            )

        iso_match = re.fullmatch(
            r"\s*(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s*",
            date_value,
        )
        if iso_match:
            year, month, day = iso_match.groups()
            padded_day = day.zfill(2)
            padded_month = month.zfill(2)
            variants.update(
                {
                    f"{year}-{padded_month}-{padded_day}",
                    f"{year}/{padded_month}/{padded_day}",
                    f"{padded_day}/{padded_month}/{year}",
                    f"{int(day)}/{int(month)}/{year}",
                    f"{padded_day}-{padded_month}-{year}",
                    f"{int(day)}-{int(month)}-{year}",
                }
            )

        text_match = re.fullmatch(
            r"\s*(\d{1,2})[-/\s]([A-Za-z]{3,})[-/,\s]+(\d{4})\s*",
            date_value,
        )
        if text_match:
            day, month, year = text_match.groups()
            month_number = self._month_number(month)
            variants.update(
                {
                    f"{day}-{month}-{year}",
                    f"{day} {month} {year}",
                    f"{day} {month}, {year}",
                    f"{day}/{month}/{year}",
                }
            )

            if month_number:
                padded_day = day.zfill(2)
                variants.update(
                    {
                        f"{padded_day}/{month_number}/{year}",
                        f"{month_number}/{padded_day}/{year}",
                        f"{padded_day}-{month_number}-{year}",
                        f"{month_number}-{padded_day}-{year}",
                    }
                )

        return variants

    @staticmethod
    def _month_number(month_name: str):
        month_numbers = {
            "jan": "01",
            "january": "01",
            "feb": "02",
            "february": "02",
            "mar": "03",
            "march": "03",
            "apr": "04",
            "april": "04",
            "may": "05",
            "jun": "06",
            "june": "06",
            "jul": "07",
            "july": "07",
            "aug": "08",
            "august": "08",
            "sep": "09",
            "sept": "09",
            "september": "09",
            "oct": "10",
            "october": "10",
            "nov": "11",
            "november": "11",
            "dec": "12",
            "december": "12",
        }

        return month_numbers.get(month_name.strip().lower())

    @staticmethod
    def _month_name(month_number: int):
        month_names = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]

        return month_names[int(month_number) - 1]

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

    def _assert_any_value_visible(self, values, description: str, timeout: float = 10):
        deadline = time.monotonic() + timeout
        expected_values = [
            self._normalize_text(value)
            for value in values
            if value
        ]

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()

            if any(expected in body_text for expected in expected_values):
                return

            if any(
                self._visible_field_value_contains(expected)
                for expected in expected_values
            ):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            f"Expected {description} value from {values!r} to be visible after "
            f"selection.\n{self._page_snapshot()}"
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
