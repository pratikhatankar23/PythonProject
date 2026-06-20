import re
import time
from pathlib import Path

from pageObjects.neftRegPayeeOnetime import NeftRegPayeeOnetimePage


class OwnAcctOnetimePaymentPage(NeftRegPayeeOnetimePage):
    OWN_ACCOUNT_TRANSFER_PATTERN = re.compile(
        r"^\s*Own\s+Account\s+Transfer\s*$",
        re.I,
    )

    def own_account_onetime_payment(self, transfer_data):
        try:
            self._handle_post_login_popups()
            self.navigate_to_own_account_transfer()
            self.enter_own_account_transfer_details(transfer_data)
            self.verify_own_account_review_transaction(transfer_data)
            self.proceed_to_pay_and_confirm_if_required(transfer_data.get("otp"))
            self.assert_transferred_successfully()
        except Exception as exc:
            artifact_dir = self._save_debug_artifacts()
            error_message = str(exc)
            if not isinstance(exc, AssertionError):
                error_message = f"{type(exc).__name__}: {exc}"

            raise AssertionError(
                f"{error_message}\n\nDebug artifacts saved to: {artifact_dir.resolve()}"
            ) from None

    def navigate_to_own_account_transfer(self):
        last_error = None

        for attempt in range(2):
            self._hover_menu_item("Payments")
            self._hover_menu_item("Single Payments")
            self._click_own_account_transfer()

            try:
                self._wait_for_own_account_transfer_screen(timeout=45)
                return
            except AssertionError as exc:
                last_error = exc
                self._reset_dropdown_state()
                self.page.wait_for_timeout(1000 * (attempt + 1))

        raise last_error

    def enter_own_account_transfer_details(self, transfer_data):
        self._select_transfer_to_account(transfer_data["to_account"])
        self._select_own_transfer_from_account(transfer_data["from_account"])

        amount = self._find_transfer_amount_field()
        self._type_like_user(amount, transfer_data["amount"], verify_value=False)

        remarks = self._find_remarks_field()
        self._type_like_user(remarks, transfer_data["remarks"])

        self._select_radio_option(
            transfer_data["transfer_schedule"],
            "Transfer schedule",
        )

        self._click_action(
            re.compile(r"^\s*Proceed\s*$", re.I),
            "Proceed button",
            value_fragments=("Proceed",),
        )
        self._wait_for_review_transaction_or_fail(timeout=45)

    def verify_own_account_review_transaction(self, transfer_data):
        deadline = time.monotonic() + 30
        missing_values = []
        review_text = ""

        while time.monotonic() < deadline:
            review_text = self._normalized_body_text()
            missing_values = self._missing_own_account_review_values(
                transfer_data,
                review_text,
            )

            if not missing_values:
                return

            self.page.wait_for_timeout(500)

        review_text = self._normalized_body_text()
        missing_values = self._missing_own_account_review_values(
            transfer_data,
            review_text,
        )

        if missing_values:
            raise AssertionError(
                "Review Transaction page is missing expected own account transfer "
                f"value(s): {missing_values}\n\nReview text:\n{review_text}"
            )

    def proceed_to_pay_and_confirm_if_required(self, otp: str | None):
        self._click_action(
            re.compile(r"^\s*Proceed\s+to\s+Pay\s*$", re.I),
            "Proceed to Pay button",
            value_fragments=("Proceed", "Pay"),
            timeout=30,
        )

        if self._transfer_success_visible(timeout=5):
            return

        if not otp:
            return

        try:
            self._find_otp_fields(len(otp), timeout=5)
        except AssertionError:
            if self._transfer_success_visible(timeout=5):
                return
            return

        self._fill_otp(otp)
        self._click_action(
            self.CONFIRM_AND_PROCEED_PATTERN,
            "Confirm and Proceed button on OTP popup",
            value_fragments=("Confirm", "Proceed"),
            timeout=30,
        )

    def _click_own_account_transfer(self, timeout: float = 30):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                menu_item = self._visible_enabled_first(
                    [
                        frame.locator("li.level-1 span").filter(
                            has_text=self.OWN_ACCOUNT_TRANSFER_PATTERN
                        ),
                        frame.locator("li.level-1 div.text-css1").filter(
                            has_text=self.OWN_ACCOUNT_TRANSFER_PATTERN
                        ),
                        frame.locator("ul.innersubmenucssnew li span").filter(
                            has_text=self.OWN_ACCOUNT_TRANSFER_PATTERN
                        ),
                        frame.locator("span").filter(
                            has_text=self.OWN_ACCOUNT_TRANSFER_PATTERN
                        ),
                        frame.locator("div.text-css1").filter(
                            has_text=self.OWN_ACCOUNT_TRANSFER_PATTERN
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
            "Could not find Own Account Transfer submenu item.\n"
            f"{self._page_snapshot()}\n\n{self._action_snapshot()}"
        )

    def _wait_for_own_account_transfer_screen(self, timeout: float = 45):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()
            error_match = self.TRANSFER_ERROR_PATTERN.search(body_text)
            transfer_form_ready = (
                self._find_transfer_to_field_optional(timeout=1)
                and self._find_own_transfer_from_field_optional(timeout=1)
            )

            if error_match and not transfer_form_ready:
                raise AssertionError(
                    "Own Account Transfer screen showed a transfer error: "
                    f"{error_match.group(0)}\n\nPage text:\n{body_text}"
                )

            if transfer_form_ready:
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for Own Account Transfer screen.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _select_transfer_to_account(self, to_account: str):
        self._select_own_account_dropdown_with_retry(
            self._find_transfer_to_field,
            to_account,
            "Transfer To dropdown",
        )
        self._assert_value_visible(to_account, "selected Transfer To account")

    def _select_own_transfer_from_account(self, from_account: str):
        self._select_own_account_dropdown_with_retry(
            self._find_own_transfer_from_field,
            from_account,
            "Transfer From dropdown",
        )
        self._assert_value_visible(from_account, "selected Transfer From account")

    def _select_own_account_dropdown_with_retry(
        self,
        field_factory,
        account_number: str,
        description: str,
        attempts: int = 3,
    ):
        last_error = None

        for attempt in range(1, attempts + 1):
            field = field_factory()

            try:
                self._select_dropdown_option(
                    field,
                    account_number,
                    description,
                    option_text=account_number,
                    choose_first_filtered=False,
                    allow_keyboard_fallback=False,
                )
                return
            except AssertionError as exc:
                last_error = exc

                if "Could not find dropdown option containing" not in str(exc):
                    raise

                self._reset_dropdown_state()
                self.page.wait_for_timeout(1000 * attempt)

        raise last_error

    def _reset_dropdown_state(self):
        for key in ("Escape", "Tab"):
            try:
                self.page.keyboard.press(key)
                self.page.wait_for_timeout(300)
            except Exception:
                pass

        self._dismiss_blocking_overlays()

    def _find_transfer_to_field(self):
        field = self._find_transfer_to_field_optional(timeout=30)

        if field:
            return field

        raise AssertionError(
            "Could not find Transfer To field.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _find_transfer_to_field_optional(self, timeout: float = 1):
        label = re.compile(r"Transfer\s+To", re.I)

        return self._find_visible_field_optional(
            [
                lambda frame: frame.get_by_label(label),
                lambda frame: frame.get_by_placeholder(label),
                lambda frame: frame.get_by_role("combobox", name=label),
                lambda frame: frame.get_by_role("textbox", name=label),
                lambda frame: frame.locator(
                    'input[aria-label*="Transfer To" i], '
                    'input[placeholder*="Transfer To" i], '
                    'input[id*="to" i][id*="account" i], '
                    'input[name*="to" i][name*="account" i], '
                    '[role="combobox"][aria-label*="Transfer To" i]'
                ),
                lambda frame: self._nearby_field_candidate(frame, label),
            ],
            timeout=timeout,
        )

    def _find_own_transfer_from_field(self):
        field = self._find_own_transfer_from_field_optional(timeout=30)

        if field:
            return field

        raise AssertionError(
            "Could not find Transfer From field.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _find_own_transfer_from_field_optional(self, timeout: float = 1):
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
                    'input[id*="from" i][id*="account" i], '
                    'input[name*="from" i][name*="account" i], '
                    '[role="combobox"][aria-label*="Transfer From" i]'
                ),
                lambda frame: self._nearby_field_candidate(frame, label),
            ],
            timeout=timeout,
        )

    def _missing_own_account_review_values(self, transfer_data, review_text):
        expected_value_groups = [
            ("Review Transaction",),
            ("Transfer From",),
            (transfer_data["from_account"],),
            ("Transfer To",),
            (transfer_data["to_account"],),
            ("Transfer Amount",),
            tuple(self._amount_review_variants(transfer_data["amount"])),
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

    def _transfer_success_visible(self, timeout: float = 5):
        success_text = re.compile(
            r"(Transferred\s+successfully|Transfer\s+successful|"
            r"Transaction\s+successful|Payment\s+successful)",
            re.I,
        )
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if success_text.search(self._normalized_body_text()):
                return True

            self.page.wait_for_timeout(500)

        return False

    def _save_debug_artifacts(self) -> Path:
        artifact_dir = (
            Path("artifacts")
            / f"own_acct_onetime_payment_{time.strftime('%Y%m%d_%H%M%S')}"
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
