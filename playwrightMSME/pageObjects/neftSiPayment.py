import re
import time
from pathlib import Path

from pageObjects.neftRegPayeeOnetime import NeftRegPayeeOnetimePage


class NeftSiPaymentPage(NeftRegPayeeOnetimePage):
    def neft_si_payment(self, transfer_data):
        try:
            self._handle_post_login_popups()
            self.navigate_to_pay_beneficiary()
            self.enter_neft_si_payment_details(transfer_data)
            self.verify_neft_si_review_transaction(transfer_data)
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

    def enter_neft_si_payment_details(self, transfer_data):
        self._arm_verify_recipient_name_click_guard()
        self._select_beneficiary(transfer_data["payeename"])
        self._select_transfer_from_account(transfer_data["from_account"])
        self._dismiss_blocking_overlays()
        self._assert_verify_recipient_name_not_clicked()

        amount = self._find_transfer_amount_field()
        self._type_like_user(amount, transfer_data["amount"], verify_value=False)

        self._select_radio_option(
            transfer_data["transfer_type"],
            "Transfer type",
        )
        self._select_radio_option(
            transfer_data["transfer_schedule"],
            "Transfer schedule",
        )
        self._wait_for_si_schedule_fields(timeout=30)

        self._select_frequency(transfer_data["frequency"])
        self._enter_start_date(transfer_data["start_date"])
        self._select_radio_option(
            transfer_data["si_instruction_schedule"],
            "Standing instruction schedule",
        )

        remarks = self._find_remarks_field()
        self._type_like_user(remarks, transfer_data["remarks"])
        self._assert_verify_recipient_name_not_clicked()

        self._click_action(
            re.compile(r"^\s*Proceed\s*$", re.I),
            "Proceed button",
            value_fragments=("Proceed",),
        )
        self._wait_for_review_transaction_or_fail(timeout=45)

    def verify_neft_si_review_transaction(self, transfer_data):
        deadline = time.monotonic() + 30
        missing_values = []
        review_text = ""

        while time.monotonic() < deadline:
            review_text = self._normalized_body_text()
            missing_values = self._missing_neft_si_review_values(
                transfer_data,
                review_text,
            )

            if not missing_values:
                return

            self.page.wait_for_timeout(500)

        review_text = self._normalized_body_text()
        missing_values = self._missing_neft_si_review_values(
            transfer_data,
            review_text,
        )

        if missing_values:
            raise AssertionError(
                "Review Transaction page is missing expected NEFT SI value(s): "
                f"{missing_values}\n\nReview text:\n{review_text}"
            )

    def assert_transferred_successfully(self):
        success_text = re.compile(
            r"(Transferred\s+successfully|Transfer\s+successful|"
            r"Transaction\s+successful|Payment\s+successful|"
            r"Standing\s+Instruction\s+.*success|"
            r"standing\s+instruction\s+.*created|"
            r"scheduled\s+successfully)",
            re.I,
        )
        self._wait_for_transfer_final_confirmation_or_fail(success_text, timeout=45)

    def _wait_for_si_schedule_fields(self, timeout: float = 30):
        deadline = time.monotonic() + timeout
        schedule_pattern = re.compile(
            r"(Select\s+Frequency|Frequency|Start\s+Date|"
            r"Standing\s+instruction\s+schedule)",
            re.I,
        )

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()
            error_match = self.TRANSFER_ERROR_PATTERN.search(body_text)

            if error_match and not schedule_pattern.search(body_text):
                raise AssertionError(
                    "NEFT SI schedule fields failed to load: "
                    f"{error_match.group(0)}\n\nPage text:\n{body_text}"
                )

            if schedule_pattern.search(body_text) and self._find_frequency_field_optional():
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for recurring payment fields after selecting "
            f"Recurring Payment.\n{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _select_frequency(self, frequency: str):
        frequency_field = self._find_frequency_field()
        self._select_dropdown_option(
            frequency_field,
            frequency,
            "Select Frequency dropdown",
            option_text=frequency,
            choose_first_filtered=False,
            allow_keyboard_fallback=True,
        )
        self._assert_value_visible(frequency, "selected frequency")

    def _find_frequency_field(self):
        field = self._find_frequency_field_optional(timeout=30)

        if field:
            return field

        raise AssertionError(
            "Could not find Select Frequency field.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _find_frequency_field_optional(self, timeout: float = 1):
        label = re.compile(r"(?:Select\s+)?Frequency", re.I)

        return self._find_visible_field_optional(
            [
                lambda frame: frame.get_by_label(label),
                lambda frame: frame.get_by_placeholder(label),
                lambda frame: frame.get_by_role("combobox", name=label),
                lambda frame: frame.get_by_role("textbox", name=label),
                lambda frame: frame.locator(
                    'input[aria-label*="Frequency" i], '
                    'input[placeholder*="Frequency" i], '
                    'input[id*="frequency" i], input[name*="frequency" i], '
                    '[role="combobox"][aria-label*="Frequency" i], '
                    'oj-select-single[aria-label*="Frequency" i], '
                    'oj-select-one[aria-label*="Frequency" i]'
                ),
                lambda frame: self._nearby_field_candidate(frame, label),
            ],
            timeout=timeout,
        )

    def _enter_start_date(self, start_date: str):
        start_date_field = self._find_start_date_field()
        self._type_like_user(start_date_field, start_date, verify_value=False)

        try:
            start_date_field.press("Tab")
        except Exception:
            pass

        self._assert_any_value_visible(
            self._date_review_variants(start_date),
            "selected Start Date",
        )

    def _find_start_date_field(self):
        label = re.compile(r"Start\s+Date", re.I)

        return self._find_visible_field(
            [
                lambda frame: frame.get_by_label(label),
                lambda frame: frame.get_by_placeholder(label),
                lambda frame: frame.get_by_role("textbox", name=label),
                lambda frame: frame.locator(
                    'input[aria-label*="Start Date" i], '
                    'input[placeholder*="Start Date" i], '
                    'input[id*="start" i][id*="date" i], '
                    'input[name*="start" i][name*="date" i], '
                    'oj-input-date input, oj-date-picker input, '
                    'input[class*="date" i]'
                ),
                lambda frame: self._nearby_field_candidate(frame, label),
            ],
            "Start Date field",
        )

    def _missing_neft_si_review_values(self, transfer_data, review_text):
        amount = transfer_data["amount"]
        amount_with_decimal = f"{float(amount):.2f}" if self._is_number(amount) else amount
        expected_value_groups = [
            (transfer_data["payeename"],),
            (transfer_data["from_account"],),
            (amount, amount_with_decimal, f"INR {amount_with_decimal}"),
            (transfer_data["transfer_type"],),
            (transfer_data["frequency"],),
            tuple(self._date_review_variants(transfer_data["start_date"])),
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

    def _date_review_variants(self, date_value: str):
        variants = {date_value}
        match = re.fullmatch(
            r"\s*(\d{1,2})[-/\s]([A-Za-z]{3,})[-/\s](\d{4})\s*",
            date_value,
        )

        if match:
            day, month, year = match.groups()
            month_number = self._month_number(month)
            variants.update(
                {
                    f"{day}-{month}-{year}",
                    f"{day} {month} {year}",
                    f"{day} {month}, {year}",
                    f"{day}/{month}/{year}",
                }
            )

            if month_number:
                padded_day = day.zfill(2)
                variants.update(
                    {
                        f"{padded_day}/{month_number}/{year}",
                        f"{month_number}/{padded_day}/{year}",
                        f"{padded_day}-{month_number}-{year}",
                        f"{month_number}-{padded_day}-{year}",
                    }
                )

        return variants

    def _assert_any_value_visible(self, values, description: str, timeout: float = 10):
        normalized_values = [self._normalize_text(value) for value in values]
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()

            if any(value in body_text for value in normalized_values):
                return

            if any(self._visible_field_value_contains(value) for value in normalized_values):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            f"Expected {description} to contain one of {tuple(values)!r}.\n"
            f"{self._page_snapshot()}"
        )

    @staticmethod
    def _month_number(month_name: str):
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

        return month_numbers.get(month_name.strip().lower())

    def _save_debug_artifacts(self) -> Path:
        artifact_dir = Path("artifacts") / f"neft_si_payment_{time.strftime('%Y%m%d_%H%M%S')}"
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
