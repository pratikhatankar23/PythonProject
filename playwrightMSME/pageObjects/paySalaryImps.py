import time
from pathlib import Path

from pageObjects.paySalaryNeft import PaySalaryNeftPage


class PaySalaryImpsPage(PaySalaryNeftPage):
    def pay_salary_imps(self, salary_data):
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

    def _save_debug_artifacts(self) -> Path:
        artifact_dir = Path("artifacts") / f"pay_salary_imps_{time.strftime('%Y%m%d_%H%M%S')}"
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
