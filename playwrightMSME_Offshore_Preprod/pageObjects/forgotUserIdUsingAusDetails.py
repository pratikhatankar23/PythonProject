import re
import time
from pathlib import Path

from playwright.sync_api import Page

from pageObjects.forgotPasswordUsingAusDetails import (
    ForgotPasswordUsingAusDetailsPage,
)


class ForgotUserIdUsingAusDetailsPage(ForgotPasswordUsingAusDetailsPage):
    FORGOT_USER_ID_PATTERN = re.compile(r"^\s*Forgot\s+User\s*ID\?\s*$", re.I)
    FINAL_SUCCESS_HEADING_PATTERN = re.compile(r"\bCongratulations\b", re.I)
    FINAL_SUCCESS_MESSAGE_PATTERN = re.compile(
        r"User\s*ID\s+has\s+been\s+sent\s+to\s+your\s+registered\s+"
        r"(?:email\s+(?:and|&)\s+mobile\s+number|email|mobile\s+number)",
        re.I,
    )

    def __init__(self, page: Page, login_url: str):
        super().__init__(page, login_url)

    def forgot_user_id_using_aus_details(self, forgot_user_id_data):
        try:
            self.open_login_page()
            self.click_forgot_user_id()
            self.accept_terms_and_select_authentication_method(forgot_user_id_data)
            self.enter_authorised_signatory_details(forgot_user_id_data)

            if not self.final_confirmation_visible(timeout=8):
                self.confirm_otp_if_displayed(forgot_user_id_data)

            self.assert_user_id_sent_successfully()
        except Exception as exc:
            artifact_dir = self._save_debug_artifacts()
            error_message = str(exc)
            if not isinstance(exc, AssertionError):
                error_message = f"{type(exc).__name__}: {exc}"

            raise AssertionError(
                f"{error_message}\n\nDebug artifacts saved to: {artifact_dir.resolve()}"
            ) from None

    def click_forgot_user_id(self):
        self._click_action(
            self.FORGOT_USER_ID_PATTERN,
            "Forgot User ID link",
            value_fragments=("Forgot User ID",),
            timeout=30,
        )

        try:
            self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        self.page.wait_for_timeout(1000)
        self._wait_for_body_text(
            re.compile(
                r"Forgot\s+User\s*ID|Terms\s*&?\s*Conditions|"
                r"Authentication\s+Method|Authori[sz]ed\s+Signatory",
                re.I,
            ),
            "Forgot User ID authentication method screen",
            timeout=30,
        )

    def enter_authorised_signatory_details(self, forgot_user_id_data):
        customer_id = self._find_customer_id_field()
        self._fill_text_field(customer_id, forgot_user_id_data["customerId"])

        pan = self._find_pan_field()
        self._fill_text_field(pan, forgot_user_id_data["pan"])

        dob = self._find_dob_field()
        self._fill_date_field(dob, forgot_user_id_data["dob"])

        country_code, mobile_number = self._find_forgot_password_mobile_fields()
        self._select_country_code(country_code, forgot_user_id_data["countryCode"])
        self._fill_text_field(mobile_number, forgot_user_id_data["mobileNumber"])

        email = self._find_email_field()
        self._fill_text_field(email, forgot_user_id_data["emailId"])

        self._click_proceed("Proceed button on Authorised Signatory details screen")
        self._wait_for_user_id_result_or_otp(timeout=45)

    def confirm_otp_if_displayed(self, forgot_user_id_data):
        for _ in range(2):
            if self.final_confirmation_visible(timeout=5):
                return

            otp_channel = self._visible_otp_channel(timeout=10)
            if not otp_channel:
                break

            otp = (
                forgot_user_id_data["emailOtp"]
                if otp_channel == "email"
                else forgot_user_id_data["mobileOtp"]
            )
            self._fill_otp(otp)
            self._click_action(
                self.CONFIRM_AND_PROCEED_PATTERN,
                "Confirm and Proceed button on OTP popup",
                value_fragments=("Confirm", "Proceed"),
                timeout=30,
            )

        if not self.final_confirmation_visible(timeout=30):
            raise AssertionError(
                "OTP confirmation completed or was not displayed, but the final "
                "Forgot User ID confirmation screen was not shown.\n"
                f"{self._page_snapshot()}"
            )

    def assert_user_id_sent_successfully(self):
        if self.final_confirmation_visible(timeout=60):
            return

        raise AssertionError(
            "Final confirmation screen with Congratulations / User ID sent "
            "success message was not displayed.\n"
            f"{self._page_snapshot()}"
        )

    def final_confirmation_visible(self, timeout: float = 5):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if self._visible_final_confirmation_present():
                return True

            self.page.wait_for_timeout(500)

        return self._visible_final_confirmation_present()

    def _visible_final_confirmation_present(self):
        for frame in self.page.frames:
            heading = self._visible_first(
                [
                    frame.get_by_text(self.FINAL_SUCCESS_HEADING_PATTERN),
                    frame.locator("h1, h2, h3, div, span").filter(
                        has_text=self.FINAL_SUCCESS_HEADING_PATTERN
                    ),
                ]
            )
            message = self._visible_first(
                [
                    frame.get_by_text(self.FINAL_SUCCESS_MESSAGE_PATTERN),
                    frame.locator("div, span, p").filter(
                        has_text=self.FINAL_SUCCESS_MESSAGE_PATTERN
                    ),
                ]
            )

            if heading and message:
                return True

        return False

    def _wait_for_user_id_result_or_otp(self, timeout: float = 45):
        otp_pattern = re.compile(
            r"Verify\s+otp|Enter\s+OTP|OTP|Confirm\s*(?:and|&)\s*Proceed",
            re.I,
        )
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()

            if self.final_confirmation_visible(timeout=1) or otp_pattern.search(body_text):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for Forgot User ID confirmation or OTP screen.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _save_debug_artifacts(self) -> Path:
        artifact_dir = (
            Path("artifacts")
            / f"forgot_user_id_using_aus_details_{time.strftime('%Y%m%d_%H%M%S')}"
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
