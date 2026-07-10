import re
import time
from pathlib import Path

from playwright.sync_api import Page

from pageObjects.addYesBankBene import AddYesBankBenePage


class ForgotPasswordUsingAusDetailsPage(AddYesBankBenePage):
    FORGOT_PASSWORD_PATTERN = re.compile(r"^\s*Forgot\s+Password\?\s*$", re.I)
    PROCEED_PATTERN = re.compile(r"^\s*Proceed\s*$", re.I)
    CONFIRM_AND_PROCEED_PATTERN = re.compile(
        r"^\s*Confirm\s*(?:and|&)\s*Proceed\s*$",
        re.I,
    )
    FINAL_SUCCESS_PATTERN = re.compile(
        r"(Congratulations|Your\s+password\s+is\s+reset\s+successfully|"
        r"password\s+reset\s+successfully|password\s+is\s+reset\s+successfully)",
        re.I,
    )
    ERROR_PATTERN = re.compile(
        r"(unable\s+to\s+process|failed|invalid|required|please\s+enter|"
        r"please\s+select|does\s+not\s+match|mismatch|expired|locked)",
        re.I,
    )

    def __init__(self, page: Page, login_url: str):
        super().__init__(page)
        self.login_url = login_url

    def forgot_password_using_aus_details(self, forgot_password_data):
        try:
            self.open_login_page()
            self.click_forgot_password()
            self.enter_user_id_and_proceed(forgot_password_data["userId"])
            self.accept_terms_and_select_authentication_method(forgot_password_data)
            self.enter_authorised_signatory_details(forgot_password_data)
            self.enter_password_details_and_proceed(forgot_password_data)

            if not self.final_confirmation_visible(timeout=8):
                self.confirm_otp_if_displayed(forgot_password_data)

            self.assert_password_reset_successfully()
        except Exception as exc:
            artifact_dir = self._save_debug_artifacts()
            error_message = str(exc)
            if not isinstance(exc, AssertionError):
                error_message = f"{type(exc).__name__}: {exc}"

            raise AssertionError(
                f"{error_message}\n\nDebug artifacts saved to: {artifact_dir.resolve()}"
            ) from None

    def open_login_page(self):
        self.page.context.clear_cookies()
        self.page.goto("about:blank")
        self.page.goto(self.login_url, wait_until="load", timeout=60000)

        try:
            self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        self._wait_for_body_text(
            re.compile(r"User\s*ID|Forgot\s+Password|Login", re.I),
            "login page",
            timeout=30,
        )

    def click_forgot_password(self):
        self._click_action(
            self.FORGOT_PASSWORD_PATTERN,
            "Forgot Password link",
            value_fragments=("Forgot Password",),
            timeout=30,
        )

        try:
            self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        self.page.wait_for_timeout(1000)
        self._wait_for_body_text(
            re.compile(r"Forgot\s+Password|User\s*ID", re.I),
            "Forgot Password User ID screen",
            timeout=30,
        )

    def enter_user_id_and_proceed(self, user_id: str):
        user_id_field = self._find_field_by_label(
            re.compile(r"User\s*ID|Login\s*ID", re.I),
            "User ID field on Forgot Password screen",
        )
        self._fill_text_field(user_id_field, user_id)
        self._click_proceed("Proceed button on Forgot Password User ID screen")
        self._wait_for_body_text(
            re.compile(
                r"Terms\s*&?\s*Conditions|Authentication\s+Method|"
                r"Authori[sz]ed\s+Signatory",
                re.I,
            ),
            "authentication method screen",
            timeout=45,
        )

    def accept_terms_and_select_authentication_method(self, forgot_password_data):
        if self._normalize_text(forgot_password_data.get("acceptTandC")) == "y":
            self._select_terms_and_conditions_checkbox()

        self._select_authentication_method(
            forgot_password_data["authenticationMethod"]
        )
        self._wait_for_body_text(
            re.compile(r"Customer\s*ID|PAN|DOB|Date\s+of\s+Birth", re.I),
            "Authorised Signatory details screen",
            timeout=45,
        )

    def enter_authorised_signatory_details(self, forgot_password_data):
        customer_id = self._find_customer_id_field()
        self._fill_text_field(customer_id, forgot_password_data["customerId"])

        pan = self._find_pan_field()
        self._fill_text_field(pan, forgot_password_data["pan"])

        dob = self._find_dob_field()
        self._fill_date_field(dob, forgot_password_data["dob"])

        country_code, mobile_number = self._find_forgot_password_mobile_fields()
        self._select_country_code(country_code, forgot_password_data["countryCode"])
        self._fill_text_field(mobile_number, forgot_password_data["mobileNumber"])

        email = self._find_email_field()
        self._fill_text_field(email, forgot_password_data["emailId"])

        self._click_proceed("Proceed button on Authorised Signatory details screen")
        self._wait_for_body_text(
            re.compile(r"Enter\s+Password|Confirm\s+Password|Password\s+matched", re.I),
            "password reset screen",
            timeout=45,
        )

    def enter_password_details_and_proceed(self, forgot_password_data):
        enter_password = self._find_password_field(
            re.compile(r"Enter\s+Password|New\s+Password", re.I),
            "Enter Password field",
            fallback_index=0,
        )
        self._type_like_user(
            enter_password,
            forgot_password_data["enterPassword"],
            verify_value=False,
        )

        confirm_password = self._find_password_field(
            re.compile(r"Confirm\s+Password|Re[-\s]?enter\s+Password", re.I),
            "Confirm Password field",
            fallback_index=1,
        )
        self._type_like_user(
            confirm_password,
            forgot_password_data["confirmPassword"],
            verify_value=False,
        )

        self._wait_for_password_matched(timeout=20)
        self._click_proceed("Proceed button on password reset screen")

    def confirm_otp_if_displayed(self, forgot_password_data):
        for _ in range(2):
            if self.final_confirmation_visible(timeout=5):
                return

            otp_channel = self._visible_otp_channel(timeout=10)
            if not otp_channel:
                break

            otp = (
                forgot_password_data["emailOtp"]
                if otp_channel == "email"
                else forgot_password_data["mobileOtp"]
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
                "password reset confirmation screen was not shown.\n"
                f"{self._page_snapshot()}"
            )

    def assert_password_reset_successfully(self):
        if self.final_confirmation_visible(timeout=60):
            return

        raise AssertionError(
            "Final confirmation screen with Congratulations / password reset "
            "success message was not displayed.\n"
            f"{self._page_snapshot()}"
        )

    def final_confirmation_visible(self, timeout: float = 5):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()

            if self.FINAL_SUCCESS_PATTERN.search(body_text):
                return True

            self.page.wait_for_timeout(500)

        return self.FINAL_SUCCESS_PATTERN.search(self._normalized_body_text()) is not None

    def _click_proceed(self, description: str):
        self._click_action(
            self.PROCEED_PATTERN,
            description,
            value_fragments=("Proceed",),
            timeout=30,
        )

    def _fill_text_field(self, field, value: str, verify_value: bool = True):
        field.click(timeout=10000)

        try:
            field.fill("")
            field.fill(value)
        except Exception:
            field.press("Control+A")
            field.press("Backspace")

            try:
                field.press_sequentially(value, delay=75)
            except AttributeError:
                field.type(value, delay=75)

        try:
            actual_value = field.input_value(timeout=1000)
        except Exception:
            actual_value = value

        is_masked_value = bool(actual_value) and set(actual_value) <= {"*"}

        if verify_value and actual_value != value and not is_masked_value:
            raise AssertionError(
                f"Expected field value to be {value!r}, but browser has {actual_value!r}."
            )

        field.press("Tab")

    def _find_forgot_password_mobile_fields(self, timeout: float = 30):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                country = self._visible_enabled_first(
                    [
                        frame.locator("#oj-select-choice-oj-select-1"),
                        frame.locator(".mobileNo [role='combobox']"),
                        frame.locator("oj-select-one").filter(
                            has_text=re.compile(r"\+\d+")
                        ),
                        frame.get_by_role("combobox").filter(
                            has_text=re.compile(r"\+\d+")
                        ),
                    ]
                )
                mobile = self._visible_enabled_first(
                    [
                        frame.get_by_placeholder(
                            re.compile(r"Please\s+Enter\s+Mobile\s+Number", re.I)
                        ),
                        frame.locator('input[placeholder*="Mobile Number" i]'),
                        frame.locator('input[id*="mobile" i]'),
                        frame.locator('input[name*="mobile" i]'),
                    ]
                )

                if country and mobile:
                    return country, mobile

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Could not find Mobile Number country code and mobile input fields.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _find_customer_id_field(self):
        return self._find_visible_input(
            [
                lambda frame: frame.locator(
                    'input[placeholder*="Customer ID" i], '
                    'input[title*="Customer ID" i]'
                ),
                lambda frame: frame.get_by_placeholder(
                    re.compile(r"Customer\s*ID", re.I)
                ),
            ],
            "Customer ID field",
        )

    def _find_pan_field(self):
        return self._find_visible_input(
            [
                lambda frame: frame.locator(
                    'input[placeholder*="Enter Pan" i], '
                    'input[title*="Enter Pan" i]'
                ),
                lambda frame: frame.get_by_placeholder(
                    re.compile(r"Enter\s+Pan|PAN", re.I)
                ),
            ],
            "PAN field",
        )

    def _find_dob_field(self):
        return self._find_visible_input(
            [
                lambda frame: frame.locator('#account-date\\|input'),
                lambda frame: frame.locator(
                    'input[id*="date" i][placeholder*="Enter" i], '
                    'input[role="combobox"][placeholder*="Enter" i]'
                ),
            ],
            "DOB field",
        )

    def _find_email_field(self):
        return self._find_visible_input(
            [
                lambda frame: frame.locator(
                    'input[placeholder*="Email ID" i], '
                    'input[title*="Email ID" i]'
                ),
                lambda frame: frame.get_by_placeholder(
                    re.compile(r"Email\s*ID|Email", re.I)
                ),
            ],
            "Email Id field",
        )

    def _find_visible_input(self, locator_factories, description: str, timeout: float = 30):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                locators = []

                for factory in locator_factories:
                    try:
                        locators.append(factory(frame))
                    except Exception:
                        continue

                field = self._visible_enabled_first(locators)

                if field:
                    return field

            self.page.wait_for_timeout(500)

        raise AssertionError(
            f"Could not find {description}.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _fill_date_field(self, field, date_value: str):
        self._fill_text_field(field, date_value, verify_value=False)

        try:
            if field.input_value(timeout=1000).strip():
                return
        except Exception:
            pass

        converted_date = self._dd_mm_yyyy_date(date_value)

        if converted_date and converted_date != date_value:
            self._fill_text_field(field, converted_date, verify_value=False)

    @staticmethod
    def _dd_mm_yyyy_date(date_value: str):
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
        match = re.fullmatch(r"\s*(\d{1,2})[-/\s]([A-Za-z]{3,})[-/,\s]+(\d{4})\s*", date_value)

        if not match:
            return None

        day, month_name, year = match.groups()
        month = month_numbers.get(month_name.casefold())

        if not month:
            return None

        return f"{day.zfill(2)}/{month}/{year}"

    def _wait_for_body_text(self, pattern, description: str, timeout: float = 45):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()

            if pattern.search(body_text):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            f"Timed out waiting for {description}.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _select_terms_and_conditions_checkbox(self):
        checkbox = self._find_terms_checkbox(timeout=20)

        try:
            if not checkbox.is_checked(timeout=1000):
                checkbox.click(timeout=5000, force=True)
                self.page.wait_for_timeout(500)
            return
        except Exception:
            pass

        try:
            checkbox.click(timeout=5000, force=True)
        except Exception:
            checkbox.evaluate("element => element.click()")

        self.page.wait_for_timeout(500)

    def _find_terms_checkbox(self, timeout: float = 20):
        terms_pattern = re.compile(r"I\s+accept|Terms\s*&?\s*Conditions|Terms", re.I)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                checkbox = self._visible_enabled_first(
                    [
                        frame.get_by_role("checkbox", name=terms_pattern),
                        frame.locator(
                            'input[type="checkbox"][aria-label*="Terms" i], '
                            'input[type="checkbox"][id*="terms" i], '
                            'input[type="checkbox"][name*="terms" i], '
                            'input[type="checkbox"]'
                        ),
                    ]
                )

                if checkbox:
                    return checkbox

                scopes = [
                    frame.locator("label").filter(has_text=terms_pattern),
                    frame.locator("oj-checkboxset").filter(has_text=terms_pattern),
                    frame.locator("span").filter(has_text=terms_pattern),
                    frame.locator("div").filter(has_text=terms_pattern),
                ]

                for scope in scopes:
                    checkbox = self._find_checkbox_in_scope(scope)
                    if checkbox:
                        return checkbox

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Could not find I accept the Terms & Conditions checkbox.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _find_checkbox_in_scope(self, scope):
        try:
            count = min(scope.count(), 6)
        except Exception:
            return None

        for index in range(count):
            candidate_scope = scope.nth(index)
            checkbox = self._visible_enabled_first(
                [
                    candidate_scope.locator('input[type="checkbox"]'),
                    candidate_scope.locator('[role="checkbox"]'),
                    candidate_scope.locator("label"),
                ]
            )

            if checkbox:
                return checkbox

        return None

    def _select_authentication_method(self, authentication_method: str):
        field = self._find_authentication_method_field_optional(timeout=5)

        if field:
            self._select_dropdown_value(
                field,
                authentication_method,
                "Authentication Method dropdown",
            )
            return

        self._click_authentication_method_card(authentication_method)

    def _find_authentication_method_field_optional(self, timeout: float = 5):
        label = re.compile(r"Authentication\s+Method|Verification\s+Method", re.I)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                field = self._visible_enabled_first(
                    [
                        frame.get_by_label(label),
                        frame.get_by_role("combobox", name=label),
                        frame.get_by_role("textbox", name=label),
                        frame.locator(
                            'input[aria-label*="Authentication" i], '
                            'input[placeholder*="Authentication" i], '
                            '[role="combobox"][aria-label*="Authentication" i], '
                            'oj-select-single[aria-label*="Authentication" i]'
                        ),
                    ]
                )

                if field:
                    return field

                fields = self._nearby_fields(frame, label)
                if fields:
                    return fields[0]

            self.page.wait_for_timeout(500)

        return None

    def _click_authentication_method_card(
        self,
        authentication_method: str,
        timeout: float = 20,
    ):
        method_pattern = self._authentication_method_pattern(authentication_method)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                clicked = self._click_authentication_method_card_in_frame(
                    frame,
                    method_pattern,
                    authentication_method,
                )

                if clicked:
                    if self._signatory_details_visible(timeout=5):
                        return

                    self.page.wait_for_timeout(500)

                option = self._visible_enabled_first(
                    [
                        frame.get_by_role("button", name=method_pattern),
                        frame.get_by_role("link", name=method_pattern),
                        frame.get_by_role("radio", name=method_pattern),
                        frame.locator("label").filter(has_text=method_pattern),
                        frame.locator("span").filter(has_text=method_pattern),
                        frame.locator("div").filter(has_text=method_pattern),
                    ]
                )

                if option:
                    try:
                        option.click(timeout=10000, force=True)
                    except Exception:
                        option.evaluate("element => element.click()")

                    if self._signatory_details_visible(timeout=5):
                        return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            f"Could not find authentication method {authentication_method!r}.\n"
            f"{self._page_snapshot()}\n\n{self._action_snapshot()}"
        )

    def _click_authentication_method_card_in_frame(
        self,
        frame,
        method_pattern,
        authentication_method: str,
    ):
        if self._click_visible_card_by_coordinates(frame, authentication_method):
            if self._signatory_details_visible(timeout=3):
                return True

        cards = frame.locator(".auth-box").filter(has_text=method_pattern)

        try:
            card_count = cards.count()
        except Exception:
            return False

        for index in range(card_count):
            card = cards.nth(index)

            try:
                if not card.is_visible():
                    continue
            except Exception:
                continue

            try:
                if frame.evaluate(
                    """
                    methodText => {
                      const normalize = value => String(value || "")
                        .replace(/\\s+/g, " ")
                        .trim()
                        .toLowerCase();
                      const requested = normalize(methodText);

                      for (const card of document.querySelectorAll(".auth-box")) {
                        if (!normalize(card.innerText || card.textContent).includes(requested)) {
                          continue;
                        }

                        const action = card.querySelector("a, button, [role='button']")
                          || card.querySelector(".icon-arrow-right")
                          || card;
                        action.scrollIntoView({block: "center", inline: "center"});
                        action.dispatchEvent(
                          new MouseEvent(
                            "click",
                            {bubbles: true, cancelable: true, view: window}
                          )
                        );
                        return true;
                      }

                      return false;
                    }
                    """,
                    authentication_method,
                ):
                    self.page.wait_for_timeout(1000)

                    if self._signatory_details_visible(timeout=2):
                        return True
            except Exception:
                pass

            action = self._visible_enabled_first(
                [
                    card.locator("a"),
                    card.locator("span.icon-arrow-right"),
                    card.locator("button"),
                    card.locator("[role='button']"),
                    card.locator(".icon-arrow-right"),
                ]
            )

            if action:
                for click_attempt in (
                    lambda: action.click(timeout=10000, force=True),
                    lambda: action.evaluate("element => element.click()"),
                ):
                    try:
                        click_attempt()
                        self.page.wait_for_timeout(1000)

                        if self._signatory_details_visible(timeout=2):
                            return True
                    except Exception:
                        continue

            try:
                box = card.bounding_box()
            except Exception:
                box = None

            if box:
                self.page.mouse.click(
                    box["x"] + box["width"] - 30,
                    box["y"] + (box["height"] / 2),
                )
                self.page.wait_for_timeout(1000)

                if self._signatory_details_visible(timeout=2):
                    return True

            try:
                card.click(timeout=10000, force=True)
                self.page.wait_for_timeout(1000)

                if self._signatory_details_visible(timeout=2):
                    return True
            except Exception:
                pass

            return True

        return False

    def _click_visible_card_by_coordinates(self, frame, authentication_method: str):
        try:
            coords = frame.evaluate(
                """
                methodText => {
                  const normalize = value => String(value || "")
                    .replace(/\\s+/g, " ")
                    .trim()
                    .toLowerCase();
                  const visible = element => {
                    if (!element) return false;
                    const style = window.getComputedStyle(element);
                    const rect = element.getBoundingClientRect();
                    return rect.width > 0
                      && rect.height > 0
                      && style.display !== "none"
                      && style.visibility !== "hidden";
                  };
                  const requested = normalize(methodText);

                  for (const card of document.querySelectorAll(".auth-box")) {
                    if (!visible(card)) continue;
                    if (!normalize(card.innerText || card.textContent).includes(requested)) {
                      continue;
                    }

                    card.scrollIntoView({block: "center", inline: "center"});
                    const action = card.querySelector("a")
                      || card.querySelector(".icon-arrow-right")
                      || card;
                    const rect = action.getBoundingClientRect();
                    return {
                      x: rect.left + (rect.width / 2),
                      y: rect.top + (rect.height / 2)
                    };
                  }

                  return null;
                }
                """,
                authentication_method,
            )
        except Exception:
            coords = None

        if not coords:
            return False

        self.page.mouse.move(coords["x"], coords["y"])
        self.page.mouse.down()
        self.page.wait_for_timeout(100)
        self.page.mouse.up()
        self.page.wait_for_timeout(1000)

        return True

    def _signatory_details_visible(self, timeout: float = 5):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                field = self._visible_enabled_first(
                    [
                        frame.locator('#custIDMobile\\|input'),
                        frame.locator('input[id*="cust" i]'),
                        frame.locator('input[id*="pan" i]'),
                        frame.locator('input[id*="date" i]'),
                        frame.locator('input[placeholder*="Enter" i]'),
                    ]
                )

                if field:
                    return True

            self.page.wait_for_timeout(500)

        return False

    def _select_dropdown_value(self, field, value: str, description: str):
        try:
            field.click(timeout=10000)
        except Exception as exc:
            raise AssertionError(f"Could not click {description}: {exc}") from None

        self.page.wait_for_timeout(500)

        search_field = self._find_active_dropdown_search_field(timeout=3) or field
        self._clear_and_type(search_field, value)
        self.page.wait_for_timeout(1000)

        option = self._find_dropdown_option(
            self._authentication_method_pattern(value),
            timeout=15,
        )

        if option:
            try:
                option.click(timeout=10000)
            except Exception:
                option.evaluate("element => element.click()")
        else:
            search_field.press("Enter")

        self.page.wait_for_timeout(1000)

        try:
            search_field.press("Tab")
        except Exception:
            pass

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

    def _find_dropdown_option(self, option_pattern, timeout: float = 15):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                option = self._visible_first(
                    [
                        frame.locator("[role='option']").filter(has_text=option_pattern),
                        frame.locator(".oj-listbox-result-label").filter(
                            has_text=option_pattern
                        ),
                        frame.locator("oj-option").filter(has_text=option_pattern),
                        frame.locator("li").filter(has_text=option_pattern),
                    ]
                )

                if option:
                    return option

            self.page.wait_for_timeout(500)

        return None

    def _clear_and_type(self, field, value: str):
        try:
            field.press("Control+A")
            field.press("Backspace")
            field.press_sequentially(value, delay=75)
        except AttributeError:
            field.type(value, delay=75)

    def _find_password_field(self, label, description: str, fallback_index: int):
        try:
            return self._find_field_by_label(label, description)
        except AssertionError:
            pass

        password_fields = []

        for frame in self.page.frames:
            fields = frame.locator('input[type="password"]')

            try:
                count = fields.count()
            except Exception:
                continue

            for index in range(count):
                field = fields.nth(index)

                try:
                    if field.is_visible() and field.is_enabled():
                        password_fields.append(field)
                except Exception:
                    continue

        if len(password_fields) > fallback_index:
            return password_fields[fallback_index]

        raise AssertionError(
            f"Could not find {description}.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _wait_for_password_matched(self, timeout: float = 20):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if self._password_matched_green():
                return

            body_text = self._normalized_body_text()
            if (
                re.search(r"password\s+matched|passwords\s+match", body_text, re.I)
                and not re.search(r"passwords?\s+do\s+not\s+match", body_text, re.I)
            ):
                return

            self.page.wait_for_timeout(500)

    def _password_matched_green(self):
        script = """
        () => {
          const visible = node => {
            const style = window.getComputedStyle(node);
            return !!(node.offsetWidth || node.offsetHeight || node.getClientRects().length)
              && style.display !== "none"
              && style.visibility !== "hidden";
          };
          const isGreen = color => {
            const match = /rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/i.exec(color || "");
            if (!match) return false;
            const red = Number(match[1]);
            const green = Number(match[2]);
            const blue = Number(match[3]);
            return green > red && green >= blue;
          };

          for (const node of document.querySelectorAll("li, div, span, p")) {
            if (!visible(node)) continue;
            const text = (node.innerText || node.textContent || "").replace(/\\s+/g, " ").trim();
            if (!/password\\s+matched|passwords\\s+match/i.test(text)) continue;

            const classText = String(node.className || "");
            if (/green|success|valid|pass/i.test(classText)) return true;
            if (/red|error|invalid|danger|fail/i.test(classText)) return false;
            if (isGreen(window.getComputedStyle(node).color)) return true;
            return true;
          }

          return false;
        }
        """

        for frame in self.page.frames:
            try:
                if frame.evaluate(script):
                    return True
            except Exception:
                continue

        return False

    def _visible_otp_channel(self, timeout: float = 10):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()

            if re.search(r"verify\s+otp.*email|email.*otp", body_text, re.I):
                return "email"

            if re.search(r"verify\s+otp.*(?:mobile|sms)|(?:mobile|sms).*otp", body_text, re.I):
                return "mobile"

            try:
                self._find_otp_fields(6, timeout=1)
                return "email"
            except AssertionError:
                pass

            self.page.wait_for_timeout(500)

        return None

    @staticmethod
    def _authentication_method_pattern(authentication_method: str):
        escaped = re.escape(authentication_method)
        escaped = escaped.replace("Authorized", "Authori[sz]ed")
        escaped = escaped.replace("Authorised", "Authori[sz]ed")
        return re.compile(rf"\b{escaped}\b", re.I)

    def _save_debug_artifacts(self) -> Path:
        artifact_dir = (
            Path("artifacts")
            / f"forgot_password_using_aus_details_{time.strftime('%Y%m%d_%H%M%S')}"
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
