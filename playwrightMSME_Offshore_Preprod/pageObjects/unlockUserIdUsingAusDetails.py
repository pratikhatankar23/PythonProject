import re
import time
from pathlib import Path

from playwright.sync_api import Page

from pageObjects.forgotPasswordUsingAusDetails import (
    ForgotPasswordUsingAusDetailsPage,
)


class UnlockUserIdUsingAusDetailsPage(ForgotPasswordUsingAusDetailsPage):
    UNLOCK_USER_ID_PATTERN = re.compile(r"\bUnlock\s+User\s*ID\??\b", re.I)
    OK_PATTERN = re.compile(r"^\s*OK\s*$", re.I)
    PASSWORD_HISTORY_PATTERN = re.compile(
        r"provided\s+new\s+password.*password\s+history|password\s+history",
        re.I,
    )
    FINAL_SUCCESS_HEADING_PATTERN = re.compile(r"\bCongratulations\b", re.I)
    FINAL_SUCCESS_MESSAGE_PATTERN = re.compile(
        r"(?:Your\s+)?(?:Login|User)\s*ID\s+has\s+been\s+successfully\s+"
        r"(?:unblocked|unlocked)|"
        r"Your\s+password\s+is\s+reset\s+successfully|"
        r"password\s+(?:is\s+)?reset\s+successfully",
        re.I,
    )

    def __init__(self, page: Page, login_url: str):
        super().__init__(page, login_url)

    def unlock_user_id_using_aus_details(self, unlock_user_id_data):
        try:
            self.open_login_page()
            self.click_unlock_user_id()
            self.enter_user_id_and_proceed(unlock_user_id_data["userId"])
            self.accept_terms_and_select_authentication_method(unlock_user_id_data)
            self.enter_authorised_signatory_details(unlock_user_id_data)
            self.enter_password_details_and_proceed(unlock_user_id_data)

            if not self.final_confirmation_visible(timeout=8):
                self.confirm_otp_if_displayed(unlock_user_id_data)

            self.assert_user_id_unlocked_successfully()
        except Exception as exc:
            artifact_dir = self._save_debug_artifacts()
            error_message = str(exc)
            if not isinstance(exc, AssertionError):
                error_message = f"{type(exc).__name__}: {exc}"

            raise AssertionError(
                f"{error_message}\n\nDebug artifacts saved to: {artifact_dir.resolve()}"
            ) from None

    def click_unlock_user_id(self):
        self._click_action(
            self.UNLOCK_USER_ID_PATTERN,
            "Unlock User ID link",
            value_fragments=("Unlock User ID",),
            timeout=30,
        )

        try:
            self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        self.page.wait_for_timeout(1000)
        self._wait_for_body_text(
            re.compile(r"Proceed", re.I),
            "Unlock User ID screen",
            timeout=30,
        )

    def enter_user_id_and_proceed(self, user_id: str):
        user_id_field = self._find_field_by_label(
            re.compile(r"User\s*ID|Login\s*ID", re.I),
            "User ID field on Unlock User ID screen",
        )
        self._fill_text_field(user_id_field, user_id)
        self._click_proceed("Proceed button on Unlock User ID screen")
        self._wait_for_body_text(
            re.compile(
                r"Terms\s*&?\s*Conditions|Authentication\s+Method|"
                r"Authori[sz]ed\s+Signatory",
                re.I,
            ),
            "authentication method screen",
            timeout=45,
        )

    def enter_password_details_and_proceed(self, unlock_user_id_data):
        generated_password = self._generated_unlock_password()
        password_candidates = [
            (
                unlock_user_id_data["enterPassword"],
                unlock_user_id_data["confirmPassword"],
            ),
            (generated_password, generated_password),
        ]

        for attempt, (enter_password, confirm_password) in enumerate(
            password_candidates,
            start=1,
        ):
            self._submit_password_details(enter_password, confirm_password)
            result = self._wait_for_unlock_result_or_otp(timeout=45)

            if result != "password_history":
                return

            self._dismiss_password_history_error()

            if attempt == len(password_candidates):
                break

        raise AssertionError(
            "Unlock User ID password submission failed because each attempted "
            "password was found in password history.\n"
            f"{self._page_snapshot()}"
        )

    def _submit_password_details(self, enter_password_value: str, confirm_password_value: str):
        enter_password = self._find_password_field(
            re.compile(r"Enter\s+Password|New\s+Password", re.I),
            "Enter Password field",
            fallback_index=0,
        )
        self._type_like_user(
            enter_password,
            enter_password_value,
            verify_value=False,
        )

        confirm_password = self._find_password_field(
            re.compile(r"Confirm\s+Password|Re[-\s]?enter\s+Password", re.I),
            "Confirm Password field",
            fallback_index=1,
        )
        self._type_like_user(
            confirm_password,
            confirm_password_value,
            verify_value=False,
        )

        self._wait_for_password_matched(timeout=20)
        self._click_proceed("Proceed button on Unlock User ID password screen")

    def confirm_otp_if_displayed(self, unlock_user_id_data):
        for _ in range(2):
            if self.final_confirmation_visible(timeout=5):
                return

            otp_channel = self._visible_otp_channel(timeout=10)
            if not otp_channel:
                break

            otp = (
                unlock_user_id_data["emailOtp"]
                if otp_channel == "email"
                else unlock_user_id_data["mobileOtp"]
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
                "Unlock User ID confirmation screen was not shown.\n"
                f"{self._page_snapshot()}"
            )

    def assert_user_id_unlocked_successfully(self):
        if self.final_confirmation_visible(timeout=60):
            return

        raise AssertionError(
            "Final confirmation screen with Congratulations / User ID unlocked "
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

    def _wait_for_unlock_result_or_otp(self, timeout: float = 45):
        otp_pattern = re.compile(
            r"Verify\s+otp|Enter\s+OTP|OTP|Confirm\s*(?:and|&)\s*Proceed",
            re.I,
        )
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()

            if self.PASSWORD_HISTORY_PATTERN.search(body_text):
                return "password_history"

            if self.final_confirmation_visible(timeout=1) or otp_pattern.search(body_text):
                return "result_or_otp"

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for Unlock User ID confirmation or OTP screen.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _dismiss_password_history_error(self):
        self._click_action(
            self.OK_PATTERN,
            "password history error OK button",
            value_fragments=("OK",),
            timeout=10,
        )
        self.page.wait_for_timeout(1000)

    @staticmethod
    def _generated_unlock_password():
        return f"Pw@{int(time.time()) % 100000000:08d}"

    def _save_debug_artifacts(self) -> Path:
        artifact_dir = (
            Path("artifacts")
            / f"unlock_user_id_using_aus_details_{time.strftime('%Y%m%d_%H%M%S')}"
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
