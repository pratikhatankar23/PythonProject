import time
from pathlib import Path

from pageObjects.neftRegPayeeOnetime import NeftRegPayeeOnetimePage


class ImpsRegPayeeOnetimePage(NeftRegPayeeOnetimePage):
    def imps_registered_payee_onetime(self, transfer_data):
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

    def _save_debug_artifacts(self) -> Path:
        artifact_dir = (
            Path("artifacts")
            / f"imps_reg_payee_onetime_{time.strftime('%Y%m%d_%H%M%S')}"
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
