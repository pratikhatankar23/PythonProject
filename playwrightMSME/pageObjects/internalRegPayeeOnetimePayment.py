import re
import time
from pathlib import Path

from pageObjects.neftRegPayeeOnetime import NeftRegPayeeOnetimePage


class InternalRegPayeeOnetimePaymentPage(NeftRegPayeeOnetimePage):
    def internal_registered_payee_onetime_payment(self, transfer_data):
        try:
            self._handle_post_login_popups()
            self.navigate_to_pay_beneficiary()
            self.enter_internal_pay_beneficiary_details(transfer_data)
            self.verify_internal_review_transaction(transfer_data)
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

    def enter_internal_pay_beneficiary_details(self, transfer_data):
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
        self._select_transfer_when_if_required(transfer_data)

        remarks = self._find_remarks_field()
        self._type_like_user(remarks, transfer_data["remarks"])
        self._assert_verify_recipient_name_not_clicked()

        self._click_action(
            re.compile(r"^\s*Proceed\s*$", re.I),
            "Proceed button",
            value_fragments=("Proceed",),
        )
        self._wait_for_review_transaction_or_fail(timeout=45)

    def verify_internal_review_transaction(self, transfer_data):
        deadline = time.monotonic() + 30
        missing_values = []
        review_text = ""

        while time.monotonic() < deadline:
            review_text = self._normalized_body_text()
            missing_values = self._missing_internal_review_values(
                transfer_data,
                review_text,
            )

            if not missing_values:
                return

            self.page.wait_for_timeout(500)

        review_text = self._normalized_body_text()
        missing_values = self._missing_internal_review_values(
            transfer_data,
            review_text,
        )

        if missing_values:
            raise AssertionError(
                "Review Transaction page is missing expected internal payment "
                f"value(s): {missing_values}\n\nReview text:\n{review_text}"
            )

    def _missing_internal_review_values(self, transfer_data, review_text):
        amount = transfer_data["amount"]
        expected_value_groups = [
            tuple(self._payee_review_variants(transfer_data["payeename"])),
            (transfer_data["from_account"],),
            tuple(self._amount_review_variants(amount)),
            (transfer_data["remarks"],),
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

        return [
            values
            for values in expected_value_groups
            if not any(self._normalize_text(value) in review_text for value in values)
        ]

    def _payee_review_variants(self, payee_name: str):
        normalized_name = self._normalize_text(payee_name)
        variants = [normalized_name]
        masked_match = re.fullmatch(r"(X+)(.+)", normalized_name, re.I)

        if masked_match:
            masked_prefix, suffix = masked_match.groups()
            min_prefix_length = max(1, len(masked_prefix) - 2)
            max_prefix_length = len(masked_prefix) + 3

            variants.extend(
                f"{'X' * prefix_length}{suffix}"
                for prefix_length in range(min_prefix_length, max_prefix_length + 1)
            )

        return list(dict.fromkeys(variants))

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
            grouped_with_decimal = self._format_indian_grouped_number(
                amount_with_decimal
            )
            grouped_without_decimal = self._format_indian_grouped_number(
                amount_without_decimal
            )
            variants.extend(
                [
                    f"INR {grouped_with_decimal}",
                    grouped_with_decimal,
                    f"INR {grouped_without_decimal}",
                    grouped_without_decimal,
                ]
            )

        return list(dict.fromkeys(variants))

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
            / f"internal_reg_payee_onetime_payment_{time.strftime('%Y%m%d_%H%M%S')}"
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
