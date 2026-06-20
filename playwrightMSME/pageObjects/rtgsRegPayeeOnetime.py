import time
from pathlib import Path

from pageObjects.neftRegPayeeOnetime import NeftRegPayeeOnetimePage


class RtgsRegPayeeOnetimePage(NeftRegPayeeOnetimePage):
    def rtgs_registered_payee_onetime(self, transfer_data):
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
            / f"rtgs_reg_payee_onetime_{time.strftime('%Y%m%d_%H%M%S')}"
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
