import re
import time
from pathlib import Path

from pageObjects.neftSiPaymentSelectEndDate import NeftSiPaymentSelectEndDatePage


class InternalSiPaymentSelectEndDatePage(NeftSiPaymentSelectEndDatePage):
    def internal_si_payment_select_end_date(self, transfer_data):
        try:
            self._handle_post_login_popups()
            self.navigate_to_pay_beneficiary()
            self.enter_internal_si_payment_select_end_date_details(transfer_data)
            self.verify_internal_si_select_end_date_review_transaction(transfer_data)
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

    def enter_internal_si_payment_select_end_date_details(self, transfer_data):
        self._arm_verify_recipient_name_click_guard()
        self._select_beneficiary(transfer_data["payeename"])
        self._select_transfer_from_account(transfer_data["from_account"])
        self._dismiss_blocking_overlays()
        self._assert_verify_recipient_name_not_clicked()

        amount = self._find_transfer_amount_field()
        self._type_like_user(amount, transfer_data["amount"], verify_value=False)

        self._select_radio_option(
            transfer_data["transfer_schedule"],
            "Transfer schedule",
        )
        self._wait_for_si_schedule_fields(timeout=30)

        self._select_frequency(transfer_data["frequency"])
        self._enter_start_date(transfer_data["start_date"])
        self._select_radio_option(
            transfer_data["si_instruction_schedule"],
            "Standing instruction Schedule",
        )
        self._wait_for_end_date_field(timeout=30)
        self._enter_end_date(transfer_data["end_date"])

        remarks = self._find_remarks_field()
        self._type_like_user(remarks, transfer_data["remarks"])
        self._assert_verify_recipient_name_not_clicked()

        self._click_action(
            re.compile(r"^\s*Proceed\s*$", re.I),
            "Proceed button",
            value_fragments=("Proceed",),
        )
        self._wait_for_review_transaction_or_fail(timeout=45)

    def verify_internal_si_select_end_date_review_transaction(self, transfer_data):
        deadline = time.monotonic() + 30
        missing_values = []
        review_text = ""

        while time.monotonic() < deadline:
            review_text = self._normalized_body_text()
            missing_values = self._missing_internal_si_select_end_date_review_values(
                transfer_data,
                review_text,
            )

            if not missing_values:
                return

            self.page.wait_for_timeout(500)

        review_text = self._normalized_body_text()
        missing_values = self._missing_internal_si_select_end_date_review_values(
            transfer_data,
            review_text,
        )

        if missing_values:
            raise AssertionError(
                "Review Transaction page is missing expected internal SI select "
                f"end-date value(s): {missing_values}\n\nReview text:\n{review_text}"
            )

    def _missing_internal_si_select_end_date_review_values(self, transfer_data, review_text):
        amount = transfer_data["amount"]
        amount_with_decimal = f"{float(amount):.2f}" if self._is_number(amount) else amount
        expected_value_groups = [
            (transfer_data["payeename"],),
            (transfer_data["from_account"],),
            (amount, amount_with_decimal, f"INR {amount_with_decimal}"),
            (transfer_data["frequency"],),
            tuple(self._date_review_variants(transfer_data["start_date"])),
            tuple(self._date_review_variants(transfer_data["end_date"])),
            (transfer_data["remarks"],),
        ]

        if re.search(r"Transfer\s+Schedule|Recurring\s+Payment", review_text, re.I):
            expected_value_groups.append((transfer_data["transfer_schedule"],))

        if re.search(r"Standing\s+instruction\s+schedule", review_text, re.I):
            expected_value_groups.append((transfer_data["si_instruction_schedule"],))

        return [
            values
            for values in expected_value_groups
            if not any(self._normalize_text(value) in review_text for value in values)
        ]

    def _save_debug_artifacts(self) -> Path:
        artifact_dir = (
            Path("artifacts")
            / f"internal_si_payment_select_end_date_{time.strftime('%Y%m%d_%H%M%S')}"
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
