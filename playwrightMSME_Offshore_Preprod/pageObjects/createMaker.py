import re
import time
from pathlib import Path

from playwright.sync_api import Page

from pageObjects.neftRegPayeeOnetime import NeftRegPayeeOnetimePage


class CreateMakerPage(NeftRegPayeeOnetimePage):
    MAKER_ERROR_PATTERN = re.compile(
        r"(maker\s+.*already\s+exists|maker\s+.*not\s+available|"
        r"login\s+id\s+.*not\s+available|user\s+.*already\s+exists|"
        r"unable\s+to\s+process|invalid\s+maker)",
        re.I,
    )
    MAKER_SUCCESS_PATTERN = re.compile(r"Maker\s+added\s+successfully", re.I)
    SUCCESS_ICON_SELECTOR = (
        "img[src*='green-checkbox' i], img[src*='green' i][src*='check' i], "
        "img[src*='success' i], img[src*='tick' i], img[src*='check' i], "
        "img[src*='verified' i], img[alt*='success' i], img[alt*='tick' i], "
        "img[alt*='check' i], img[alt*='verified' i], "
        "[aria-label*='success' i], [aria-label*='verified' i], "
        "[title*='success' i], [title*='verified' i], "
        "[class*='success' i], [class*='tick' i], [class*='check' i], "
        "[class*='verified' i]"
    )

    def __init__(self, page: Page):
        super().__init__(page)

    def create_maker(self, maker_data):
        try:
            self._handle_post_login_popups()
            self.navigate_to_add_new_maker()
            self.enter_maker_details(maker_data)
            self.configure_access_rights(maker_data)
            self.verify_summary(maker_data)
            self.submit_summary_and_confirm_otp(maker_data["otp"])
            self.assert_maker_added_successfully()
        except Exception as exc:
            artifact_dir = self._save_debug_artifacts()
            error_message = str(exc)
            if not isinstance(exc, AssertionError):
                error_message = f"{type(exc).__name__}: {exc}"

            raise AssertionError(
                f"{error_message}\n\nDebug artifacts saved to: {artifact_dir.resolve()}"
            ) from None

    def navigate_to_add_new_maker(self):
        self._hover_menu_item("Services")
        self._click_menu_item("Create Maker")
        self._wait_for_create_maker_screen(timeout=45)

    def enter_maker_details(self, maker_data):
        maker_login_id = self._find_form_field(
            re.compile(r"Maker\s+login\s+ID|Maker\s+Login\s+Id|Login\s+ID", re.I),
            "Maker login ID field",
            extra_selectors=(
                'input[aria-label*="Maker" i][aria-label*="Login" i]',
                'input[id*="maker" i][id*="login" i]',
                'input[name*="maker" i][name*="login" i]',
                'input[id*="login" i]',
            ),
        )
        self._type_like_user(maker_login_id, maker_data["makerLoginID"])
        self._click_action(
            re.compile(r"^\s*Check\s+Availability\s*$", re.I),
            "Check Availability button",
            value_fragments=("Check Availability", "Availability"),
            timeout=30,
        )
        self._assert_maker_login_available(maker_login_id)

        self._select_optional_dropdown(
            re.compile(r"^\s*Title\s*$", re.I),
            "Title field",
            maker_data.get("title"),
            extra_selectors=(
                'input[aria-label*="Title" i]',
                '[role="combobox"][aria-label*="Title" i]',
                'oj-select-single[id*="title" i]',
            ),
        )
        self._fill_mandatory_text_field(
            re.compile(r"First\s+Name", re.I),
            "First Name field",
            maker_data["firstName"],
            extra_selectors=(
                'input[aria-label*="First Name" i]',
                'input[id*="first" i][id*="name" i]',
                'input[name*="first" i][name*="name" i]',
            ),
        )
        self._fill_optional_text_field(
            re.compile(r"Middle\s+Name", re.I),
            "Middle Name field",
            maker_data.get("middleName"),
            extra_selectors=(
                'input[aria-label*="Middle Name" i]',
                'input[id*="middle" i][id*="name" i]',
                'input[name*="middle" i][name*="name" i]',
            ),
        )
        self._fill_optional_text_field(
            re.compile(r"Last\s+Name", re.I),
            "Last Name field",
            maker_data.get("lastName"),
            extra_selectors=(
                'input[aria-label*="Last Name" i]',
                'input[id*="last" i][id*="name" i]',
                'input[name*="last" i][name*="name" i]',
            ),
        )
        self._fill_mandatory_text_field(
            re.compile(r"Date\s+of\s+Birth|DOB", re.I),
            "Date of Birth field",
            maker_data["dateOfBirth"],
            extra_selectors=(
                'input[aria-label*="Date of Birth" i]',
                'input[placeholder*="Date of Birth" i]',
                'input[id*="birth" i]',
                'input[name*="birth" i]',
                'input[class*="date" i]',
            ),
            verify_value=False,
        )
        self._fill_mandatory_text_field(
            re.compile(r"Email\s+Id|Email\s+ID|Email", re.I),
            "Email Id field",
            maker_data["emailId"],
            extra_selectors=(
                'input[aria-label*="Email" i]',
                'input[id*="email" i]',
                'input[name*="email" i]',
            ),
        )

        country_code, mobile_number = self._find_mobile_contact_fields()
        self._select_dropdown_value(
            country_code,
            maker_data["countryCode"],
            "Contact Number (Mobile) country code dropdown",
            choose_first_filtered=True,
            allow_keyboard_fallback=False,
        )
        self._assert_country_code_selected(country_code, maker_data["countryCode"])
        self._type_like_user(mobile_number, maker_data["mobileNumber"])

        self._fill_optional_text_field(
            re.compile(r"Contact\s+Number\s*\(\s*Landline\s*\)|Landline", re.I),
            "Contact Number (Landline) field",
            maker_data.get("contactNumber"),
            extra_selectors=(
                'input[aria-label*="Landline" i]',
                'input[id*="landline" i]',
                'input[name*="landline" i]',
                'input[id*="contact" i][id*="number" i]',
            ),
        )
        self._fill_mandatory_text_field(
            re.compile(r"Address\s+Line\s+1", re.I),
            "Address Line 1 field",
            maker_data["addressLine1"],
            extra_selectors=(
                'input[aria-label*="Address Line 1" i]',
                'textarea[aria-label*="Address Line 1" i]',
                'input[id*="address" i][id*="1" i]',
                'textarea[id*="address" i][id*="1" i]',
            ),
        )
        self._fill_optional_text_field(
            re.compile(r"Address\s+Line\s+2", re.I),
            "Address Line 2 field",
            maker_data.get("addressLine2"),
            extra_selectors=(
                'input[aria-label*="Address Line 2" i]',
                'textarea[aria-label*="Address Line 2" i]',
                'input[id*="address" i][id*="2" i]',
                'textarea[id*="address" i][id*="2" i]',
            ),
        )
        self._fill_optional_text_field(
            re.compile(r"Address\s+Line\s+3", re.I),
            "Address Line 3 field",
            maker_data.get("addressLine3"),
            extra_selectors=(
                'input[aria-label*="Address Line 3" i]',
                'textarea[aria-label*="Address Line 3" i]',
                'input[id*="address" i][id*="3" i]',
                'textarea[id*="address" i][id*="3" i]',
            ),
        )
        self._fill_optional_text_field(
            re.compile(r"Address\s+Line\s+4", re.I),
            "Address Line 4 field",
            maker_data.get("addressLine4"),
            extra_selectors=(
                'input[aria-label*="Address Line 4" i]',
                'textarea[aria-label*="Address Line 4" i]',
                'input[id*="address" i][id*="4" i]',
                'textarea[id*="address" i][id*="4" i]',
            ),
        )
        self._enter_or_select_mandatory_field(
            re.compile(r"^\s*Country\s*$", re.I),
            "Country field",
            maker_data["country"],
            extra_selectors=(
                'input[aria-label="Country" i]',
                '[role="combobox"][aria-label="Country" i]',
                'input[id*="country" i]',
                'oj-select-single[id*="country" i]',
            ),
        )
        self._enter_or_select_mandatory_field(
            re.compile(r"^\s*City\s*$", re.I),
            "City field",
            maker_data["city"],
            extra_selectors=(
                'input[aria-label="City" i]',
                '[role="combobox"][aria-label="City" i]',
                'input[id*="city" i]',
                'oj-select-single[id*="city" i]',
            ),
        )
        self._select_optional_dropdown(
            re.compile(r"Zip\s+Code|Postal\s+Code|PIN\s+Code", re.I),
            "Zip Code field",
            maker_data.get("zipCode"),
            extra_selectors=(
                'input[aria-label*="Zip" i]',
                '[role="combobox"][aria-label*="Zip" i]',
                'input[id*="zip" i]',
                'input[name*="zip" i]',
                'oj-select-single[id*="zip" i]',
            ),
        )

        self._click_action(
            re.compile(r"^\s*Proceed\s*$", re.I),
            "Proceed button on Add New Maker screen",
            value_fragments=("Proceed",),
            timeout=30,
        )
        self._wait_for_maker_access_rights_screen(timeout=45)

    def configure_access_rights(self, maker_data):
        select_all = str(maker_data.get("accessRightsSelectAll", "")).strip().upper()

        if select_all == "Y":
            self._click_select_all_access_rights()
            self._assert_all_visible_access_rights_selected()
        else:
            self._clear_visible_access_right_checkboxes()
            for access_right in maker_data.get("accessRights", []):
                self._set_access_right_checkbox(access_right, checked=True)

        self._click_action(
            re.compile(r"^\s*Confirm\s*$", re.I),
            "Confirm button on Maker Access Rights screen",
            value_fragments=("Confirm",),
            timeout=30,
        )
        self._wait_for_summary_screen(timeout=45)

    def verify_summary(self, maker_data):
        expected_value_groups = self._summary_expected_value_groups(maker_data)
        deadline = time.monotonic() + 30
        summary_text = ""
        missing_values = expected_value_groups

        while time.monotonic() < deadline:
            summary_text = self._normalized_body_text()
            missing_values = self._missing_summary_values(
                expected_value_groups,
                summary_text,
            )

            if not missing_values:
                return

            self.page.wait_for_timeout(500)

        summary_text = self._normalized_body_text()
        missing_values = self._missing_summary_values(
            expected_value_groups,
            summary_text,
        )

        if missing_values:
            raise AssertionError(
                "Summary screen is missing expected Create Maker value(s): "
                f"{missing_values}\n\nSummary text:\n{summary_text}"
            )

    def submit_summary_and_confirm_otp(self, otp: str):
        self._click_action(
            re.compile(r"^\s*Add\s+Maker\s*$", re.I),
            "Add Maker button on Summary screen",
            value_fragments=("Add Maker",),
            timeout=30,
        )

        if self._maker_success_visible(timeout=5):
            return

        if self._otp_visible(timeout=10):
            self._fill_otp(otp)
            self._click_action(
                self.CONFIRM_AND_PROCEED_PATTERN,
                "Confirm and Proceed button on Add Maker OTP popup",
                value_fragments=("Confirm", "Proceed"),
                timeout=30,
            )

    def assert_maker_added_successfully(self):
        deadline = time.monotonic() + 45

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()
            error_match = self.MAKER_ERROR_PATTERN.search(body_text)

            if error_match and not self.MAKER_SUCCESS_PATTERN.search(body_text):
                raise AssertionError(
                    "Create Maker failed before final confirmation screen: "
                    f"{error_match.group(0)}\n\nPage text:\n{body_text}"
                )

            if self.MAKER_SUCCESS_PATTERN.search(body_text):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for Maker added successfully confirmation.\n"
            f"{self._page_snapshot()}"
        )

    def _find_form_field(
        self,
        label_pattern,
        description: str,
        extra_selectors=(),
        index: int = 0,
        timeout: float = 30,
        enabled_only: bool = True,
    ):
        locator_factories = [
            *[
                (lambda frame, selector=selector: frame.locator(selector))
                for selector in extra_selectors
            ],
            lambda frame: frame.get_by_role("textbox", name=label_pattern),
            lambda frame: frame.get_by_role("combobox", name=label_pattern),
            lambda frame: frame.get_by_placeholder(label_pattern),
            lambda frame: frame.get_by_label(label_pattern),
            lambda frame: self._nearby_field_candidate_at_index(
                frame,
                label_pattern,
                index,
            ),
        ]
        finder = (
            self._visible_enabled_form_field_first
            if enabled_only
            else self._visible_form_field_first
        )
        deadline = time.monotonic() + timeout

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

        raise AssertionError(
            f"Could not find {description}.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _visible_form_field_first(self, locators):
        return self._visible_form_field_first_matching(locators, require_enabled=False)

    def _visible_enabled_form_field_first(self, locators):
        return self._visible_form_field_first_matching(locators, require_enabled=True)

    def _visible_form_field_first_matching(self, locators, require_enabled: bool):
        for locator in locators:
            try:
                for index in range(locator.count()):
                    candidate = locator.nth(index)

                    if not candidate.is_visible():
                        continue

                    if require_enabled and not candidate.is_enabled():
                        continue

                    if self._is_form_field(candidate):
                        return candidate
            except Exception:
                continue

        return None

    def _is_form_field(self, locator):
        try:
            attrs = locator.evaluate(
                """
                e => ({
                  tag: e.tagName.toLowerCase(),
                  role: e.getAttribute("role") || "",
                  classes: e.className || "",
                  type: e.getAttribute("type") || "",
                  contentEditable: e.getAttribute("contenteditable") || ""
                })
                """
            )
        except Exception:
            return False

        tag = attrs.get("tag", "")
        role = attrs.get("role", "")
        classes = attrs.get("classes", "")

        return bool(
            tag in (
                "input",
                "textarea",
                "select",
                "oj-input-text",
                "oj-input-date",
                "oj-select-one",
                "oj-select-single",
                "oj-combobox-one",
            )
            or role in ("textbox", "combobox", "searchbox")
            or "oj-select-choice" in classes
            or attrs.get("contentEditable") == "true"
        )

    def _nearby_field_candidate_at_index(self, frame, label_pattern, index: int):
        fields = self._nearby_fields(frame, label_pattern)

        if len(fields) > index:
            return fields[index]

        return frame.locator("xpath=//*[false()]")

    def _fill_mandatory_text_field(
        self,
        label_pattern,
        description: str,
        value: str,
        extra_selectors=(),
        verify_value: bool = True,
    ):
        if not str(value or "").strip():
            raise AssertionError(f"{description} is mandatory but no value was provided.")

        field = self._find_form_field(
            label_pattern,
            description,
            extra_selectors=extra_selectors,
        )
        self._type_like_user(field, value, verify_value=verify_value)

    def _fill_optional_text_field(
        self,
        label_pattern,
        description: str,
        value,
        extra_selectors=(),
    ):
        if not str(value or "").strip():
            return

        field = self._find_form_field(
            label_pattern,
            description,
            extra_selectors=extra_selectors,
        )
        self._type_like_user(field, value)

    def _enter_or_select_mandatory_field(
        self,
        label_pattern,
        description: str,
        value: str,
        extra_selectors=(),
    ):
        if not str(value or "").strip():
            raise AssertionError(f"{description} is mandatory but no value was provided.")

        field = self._find_form_field(
            label_pattern,
            description,
            extra_selectors=extra_selectors,
        )

        if self._field_looks_like_dropdown(field):
            self._select_dropdown_value(field, value, description)
        else:
            self._type_like_user(field, value)

    def _select_optional_dropdown(
        self,
        label_pattern,
        description: str,
        value,
        extra_selectors=(),
    ):
        if not str(value or "").strip():
            return

        field = self._find_form_field(
            label_pattern,
            description,
            extra_selectors=extra_selectors,
        )
        self._select_dropdown_value(field, value, description)

    def _select_dropdown_value(
        self,
        field,
        value: str,
        description: str,
        choose_first_filtered: bool = True,
        allow_keyboard_fallback: bool = True,
    ):
        self._select_dropdown_option(
            field,
            value,
            description,
            option_text=value,
            choose_first_filtered=choose_first_filtered,
            allow_keyboard_fallback=allow_keyboard_fallback,
        )

    def _field_looks_like_dropdown(self, field):
        try:
            attrs = field.evaluate(
                """
                e => ({
                  tag: e.tagName.toLowerCase(),
                  role: e.getAttribute("role") || "",
                  ariaHasPopup: e.getAttribute("aria-haspopup") || "",
                  classes: e.className || "",
                  id: e.id || "",
                  name: e.getAttribute("name") || ""
                })
                """
            )
        except Exception:
            return False

        text = self._normalize_text(" ".join(str(value) for value in attrs.values()))
        return bool(
            "combobox" in text
            or "select" in text
            or "lov" in text
            or attrs.get("tag") in ("oj-select-single", "select")
        )

    def _find_mobile_contact_fields(self, timeout: float = 30):
        label = re.compile(r"Contact\s+Number\s*\(\s*Mobile\s*\)|Mobile", re.I)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                country = self._visible_enabled_first(
                    [
                        frame.locator(
                            'oj-select-one[value*="countryCodeVal"] [role="combobox"], '
                            'oj-select-one#oj-select-1 [role="combobox"], '
                            '#oj-select-choice-oj-select-1, '
                            'oj-select-one.dropdown-css [role="combobox"]'
                        ),
                    ]
                )
                mobile = self._visible_enabled_first(
                    [
                        frame.locator(
                            'input[id="mobile|input"], '
                            'input[aria-label*="Mobile" i], '
                            'input[aria-label*="Contact Number" i], '
                            'input[id*="mobile" i], input[name*="mobile" i], '
                            'input[type="tel"]'
                        ),
                        frame.get_by_role("textbox", name=label),
                        self._nearby_field_candidate_at_index(frame, label, 1),
                    ]
                )

                if country and mobile:
                    return country, mobile

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Could not find Contact Number (Mobile) country code and mobile "
            f"input fields.\n{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _assert_country_code_selected(self, country_code_field, expected_code: str):
        expected_digits = expected_code.lstrip("+")
        expected_patterns = (
            self._normalize_text(expected_code),
            self._normalize_text(f"+{expected_digits}"),
            self._normalize_text(expected_digits),
        )
        deadline = time.monotonic() + 10

        while time.monotonic() < deadline:
            try:
                display_text = country_code_field.evaluate(
                    """
                    e => {
                      const selected = e.querySelector && e.querySelector(".oj-select-chosen");
                      return (
                        (selected && (selected.innerText || selected.textContent)) ||
                        e.innerText ||
                        e.textContent ||
                        e.value ||
                        ""
                      ).replace(/\\s+/g, " ").trim();
                    }
                    """
                )
            except Exception:
                display_text = ""

            normalized_display = self._normalize_text(display_text)

            if any(pattern in normalized_display for pattern in expected_patterns):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Contact Number (Mobile) country code was not selected as expected. "
            f"Expected {expected_code!r}.\n{self._page_snapshot()}"
        )

    def _assert_maker_login_available(self, maker_login_id_field, timeout: float = 30):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()
            error_match = self.MAKER_ERROR_PATTERN.search(body_text)

            if error_match:
                raise AssertionError(
                    "Maker login ID availability check failed: "
                    f"{error_match.group(0)}\n\nPage text:\n{body_text}"
                )

            if self._has_visible_success_indicator(maker_login_id_field):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Green checkbox / success indicator was not displayed after clicking "
            f"Check Availability for maker login ID.\n"
            f"{self._page_snapshot()}\n\n{self._action_snapshot()}"
        )

    def _has_visible_success_indicator(self, related_field):
        scopes = []

        for xpath in (
            "xpath=ancestor::*[self::div or self::oj-form-layout][1]",
            "xpath=ancestor::*[self::div or self::oj-form-layout][2]",
            "xpath=ancestor::*[self::div or self::oj-form-layout][3]",
        ):
            try:
                scopes.append(related_field.locator(xpath))
            except Exception:
                continue

        scopes.append(self.page.locator("body"))

        for scope in scopes:
            try:
                indicator = self._visible_first(
                    [
                        scope.locator(self.SUCCESS_ICON_SELECTOR),
                        scope.locator("[style*='green' i]"),
                    ]
                )

                if indicator:
                    return True
            except Exception:
                continue

        return False

    def _wait_for_create_maker_screen(self, timeout: float = 45):
        screen_pattern = re.compile(
            r"(Add\s+New\s+Maker|Create\s+Maker|Maker\s+login\s+ID|First\s+Name)",
            re.I,
        )
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()

            if screen_pattern.search(body_text) and re.search(
                r"Maker\s+login\s+ID|First\s+Name",
                body_text,
                re.I,
            ):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for Add New Maker screen.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _wait_for_maker_access_rights_screen(self, timeout: float = 45):
        screen_pattern = re.compile(
            r"(Maker\s+Access\s+Rights|Access\s+Rights|Select\s+All|"
            r"Fund\s+Transfer\s+Maker|Salary\s+Maker)",
            re.I,
        )
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()
            error_match = self.MAKER_ERROR_PATTERN.search(body_text)

            if error_match:
                raise AssertionError(
                    "Create Maker failed before Maker Access Rights screen: "
                    f"{error_match.group(0)}\n\nPage text:\n{body_text}"
                )

            if screen_pattern.search(body_text):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for Maker Access Rights screen after clicking Proceed.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _wait_for_summary_screen(self, timeout: float = 45):
        summary_pattern = re.compile(r"(Summary|Add\s+Maker|Maker\s+Login)", re.I)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()
            error_match = self.MAKER_ERROR_PATTERN.search(body_text)

            if error_match and not summary_pattern.search(body_text):
                raise AssertionError(
                    "Create Maker failed before Summary screen: "
                    f"{error_match.group(0)}\n\nPage text:\n{body_text}"
                )

            if summary_pattern.search(body_text) and re.search(
                r"Add\s+Maker|Maker\s+Login|Email",
                body_text,
                re.I,
            ):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for Summary screen after confirming access rights.\n"
            f"{self._page_snapshot()}\n\n{self._action_snapshot()}"
        )

    def _click_select_all_access_rights(self, timeout: float = 30):
        pattern = re.compile(r"^\s*Select\s+All\s*$", re.I)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                select_all = self._visible_enabled_first(
                    [
                        frame.get_by_role("link", name=pattern),
                        frame.get_by_role("button", name=pattern),
                        frame.locator("a").filter(has_text=pattern),
                        frame.locator("button").filter(has_text=pattern),
                        frame.locator("span").filter(has_text=pattern),
                        frame.locator("div").filter(has_text=pattern),
                    ]
                )

                if not select_all:
                    continue

                try:
                    select_all.click(timeout=10000)
                except Exception:
                    select_all.evaluate("element => element.click()")

                self.page.wait_for_timeout(1000)
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Could not find Select All action on Maker Access Rights screen.\n"
            f"{self._page_snapshot()}\n\n{self._action_snapshot()}"
        )

    def _assert_all_visible_access_rights_selected(self, timeout: float = 10):
        deadline = time.monotonic() + timeout
        unchecked = []

        while time.monotonic() < deadline:
            checkbox_states = self._visible_checkbox_states()

            if checkbox_states and all(state["checked"] for state in checkbox_states):
                return

            unchecked = [
                state["text"] or state["id"] or f"checkbox-{state['index']}"
                for state in checkbox_states
                if not state["checked"]
            ]
            self.page.wait_for_timeout(500)

        if not unchecked:
            unchecked = ["No visible access-right checkboxes were detected."]

        raise AssertionError(
            "Select All did not leave every visible Maker Access Rights checkbox "
            f"selected. Unchecked: {unchecked}\n\n{self._checkbox_snapshot()}"
        )

    def _clear_visible_access_right_checkboxes(self):
        for checkbox in self._iter_visible_checkbox_controls():
            if self._is_checkbox_checked(checkbox):
                try:
                    checkbox.click(timeout=3000)
                except Exception:
                    checkbox.evaluate("element => element.click()")
                self.page.wait_for_timeout(200)

    def _set_access_right_checkbox(self, access_right: str, checked: bool = True):
        control = self._find_access_right_control(access_right)

        if self._is_checkbox_checked(control) != checked:
            try:
                control.click(timeout=10000)
            except Exception:
                control.evaluate("element => element.click()")

        self.page.wait_for_timeout(500)

        if self._is_checkbox_checked(control) != checked:
            raise AssertionError(
                f"Could not set access right {access_right!r} to {checked}.\n"
                f"{self._checkbox_snapshot()}"
            )

    def _find_access_right_control(self, access_right: str, timeout: float = 30):
        access_right = str(access_right or "").strip()
        pattern = re.compile(rf"^\s*{re.escape(access_right)}\s*$", re.I)
        contains_pattern = re.compile(re.escape(access_right), re.I)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                direct_control = self._visible_enabled_first(
                    [
                        frame.locator(
                            f'input[type="checkbox"][aria-label="{access_right}" i], '
                            f'input[type="checkbox"][value="{access_right}" i]'
                        ),
                        frame.get_by_role("checkbox", name=pattern),
                        frame.get_by_label(pattern),
                    ]
                )

                if direct_control:
                    return direct_control

                scopes = [
                    frame.locator("label").filter(has_text=contains_pattern),
                    frame.locator("tr").filter(has_text=contains_pattern),
                    frame.locator("li").filter(has_text=contains_pattern),
                    frame.locator("div").filter(has_text=contains_pattern),
                    frame.locator("oj-checkboxset").filter(has_text=contains_pattern),
                ]

                for scope_locator in scopes:
                    try:
                        count = min(scope_locator.count(), 20)
                    except Exception:
                        continue

                    for index in range(count):
                        scope = scope_locator.nth(index)

                        try:
                            if not scope.is_visible():
                                continue
                        except Exception:
                            continue

                        checkbox = self._find_checkbox_in_scope(scope)
                        if checkbox:
                            return checkbox

                        return scope

            self.page.wait_for_timeout(500)

        raise AssertionError(
            f"Could not find Maker Access Rights checkbox for {access_right!r}.\n"
            f"{self._page_snapshot()}\n\n{self._checkbox_snapshot()}"
        )

    def _find_checkbox_in_scope(self, scope):
        return self._visible_enabled_first(
            [
                scope.locator('input[type="checkbox"]'),
                scope.locator('[role="checkbox"]'),
            ]
        )

    def _iter_visible_checkbox_controls(self):
        controls = []

        for frame in self.page.frames:
            for locator in (
                frame.locator('input[type="checkbox"]'),
                frame.locator('[role="checkbox"]'),
            ):
                try:
                    count = min(locator.count(), 200)
                except Exception:
                    continue

                for index in range(count):
                    checkbox = locator.nth(index)

                    try:
                        if checkbox.is_visible() and checkbox.is_enabled():
                            controls.append(checkbox)
                    except Exception:
                        continue

        return controls

    def _visible_checkbox_states(self):
        states = []

        for index, checkbox in enumerate(self._iter_visible_checkbox_controls()):
            try:
                text = checkbox.evaluate(
                    """
                    e => {
                      const scope = e.closest("label, tr, li, div, oj-checkboxset") || e;
                      return (scope.innerText || scope.textContent || "")
                        .replace(/\\s+/g, " ")
                        .trim();
                    }
                    """
                )
            except Exception:
                text = ""

            try:
                element_id = checkbox.evaluate("e => e.id || e.getAttribute('id') || ''")
            except Exception:
                element_id = ""

            states.append(
                {
                    "index": index,
                    "id": element_id,
                    "text": text,
                    "checked": self._is_checkbox_checked(checkbox),
                }
            )

        return states

    def _is_checkbox_checked(self, checkbox):
        try:
            return bool(
                checkbox.evaluate(
                    """
                    e => {
                      const input = e.matches && e.matches("input[type='checkbox']")
                        ? e
                        : e.querySelector && e.querySelector("input[type='checkbox']");
                      const checkedValue = input ? input.checked : false;
                      const ariaChecked = e.getAttribute("aria-checked")
                        || (input && input.getAttribute("aria-checked"))
                        || "";
                      const classes = `${e.className || ""} ${input ? input.className || "" : ""}`;

                      return checkedValue
                        || ariaChecked === "true"
                        || /\\boj-selected\\b|\\boj-selected\\b|\\bchecked\\b|\\bselected\\b/i.test(classes);
                    }
                    """
                )
            )
        except Exception:
            return False

    def _summary_expected_value_groups(self, maker_data):
        country_code_digits = maker_data["countryCode"].lstrip("+")
        expected_value_groups = [
            (maker_data["makerLoginID"],),
            (maker_data["firstName"],),
            tuple(self._date_summary_variants(maker_data["dateOfBirth"])),
            (maker_data["emailId"],),
            (maker_data["countryCode"], f"+{country_code_digits}"),
            (maker_data["mobileNumber"], f"{country_code_digits}{maker_data['mobileNumber']}"),
            (maker_data["addressLine1"],),
            (maker_data["country"],),
            (maker_data["city"],),
        ]

        for key in (
            "title",
            "middleName",
            "lastName",
            "contactNumber",
            "addressLine2",
            "addressLine3",
            "addressLine4",
            "zipCode",
        ):
            value = maker_data.get(key)
            if str(value or "").strip():
                expected_value_groups.append((value,))

        if str(maker_data.get("accessRightsSelectAll", "")).strip().upper() != "Y":
            for access_right in maker_data.get("accessRights", []):
                if str(access_right or "").strip():
                    expected_value_groups.append((access_right,))
        else:
            expected_value_groups.append(("access rights", "maker access rights"))

        return expected_value_groups

    @staticmethod
    def _date_summary_variants(date_value: str):
        date_text = str(date_value or "").strip()
        variants = [date_text]

        if "-" in date_text:
            variants.append(date_text.replace("-", " "))

        return list(dict.fromkeys(value for value in variants if value))

    def _missing_summary_values(self, expected_value_groups, summary_text):
        return [
            values
            for values in expected_value_groups
            if not any(
                self._normalize_text(value) in summary_text for value in values if value
            )
        ]

    def _otp_visible(self, timeout: float = 10):
        deadline = time.monotonic() + timeout
        otp_pattern = re.compile(r"(otp|one\s*time|verification|security\s*code)", re.I)

        while time.monotonic() < deadline:
            if otp_pattern.search(self._normalized_body_text()):
                return True

            if self._maker_success_visible(timeout=1):
                return False

            self.page.wait_for_timeout(500)

        return False

    def _maker_success_visible(self, timeout: float = 5):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if self.MAKER_SUCCESS_PATTERN.search(self._normalized_body_text()):
                return True

            self.page.wait_for_timeout(500)

        return False

    def _checkbox_snapshot(self) -> str:
        rows = []
        script = """
        els => els.map((e, idx) => {
          const input = e.matches && e.matches("input[type='checkbox']")
            ? e
            : e.querySelector && e.querySelector("input[type='checkbox']");
          const scope = e.closest("label, tr, li, div, oj-checkboxset") || e;
          return {
            idx,
            tag: e.tagName.toLowerCase(),
            id: e.id || "",
            role: e.getAttribute("role") || "",
            aria: e.getAttribute("aria-checked") || "",
            checked: input ? input.checked : false,
            classes: e.className || "",
            text: (scope.innerText || scope.textContent || "")
              .trim()
              .replace(/\\s+/g, " "),
            visible: !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length)
          };
        })
        """
        selector = (
            "input[type='checkbox'], [role='checkbox'], .oj-checkbox, "
            "[class*='checkbox' i]"
        )

        for frame_index, frame in enumerate(self.page.frames):
            try:
                checkboxes = frame.locator(selector).evaluate_all(script)
            except Exception as exc:
                rows.append(f"frame={frame_index} url={frame.url} unavailable: {exc}")
                continue

            for checkbox in checkboxes:
                rows.append(
                    "frame={frame} url={url} idx={idx} tag={tag} id={id} "
                    "role={role} aria={aria} checked={checked} classes={classes} "
                    "visible={visible} text={text}".format(
                        frame=frame_index,
                        url=frame.url,
                        **checkbox,
                    )
                )

        return "\n".join(rows) or "No checkbox-like elements were found."

    def _save_debug_artifacts(self) -> Path:
        artifact_dir = Path("artifacts") / f"create_maker_{time.strftime('%Y%m%d_%H%M%S')}"
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
                    "CHECKBOXES",
                    self._checkbox_snapshot(),
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
