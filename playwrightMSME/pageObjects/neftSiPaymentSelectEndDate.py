import re
import time
from pathlib import Path

from pageObjects.neftSiPayment import NeftSiPaymentPage


class NeftSiPaymentSelectEndDatePage(NeftSiPaymentPage):
    def neft_si_payment_select_end_date(self, transfer_data):
        try:
            self._handle_post_login_popups()
            self.navigate_to_pay_beneficiary()
            self.enter_neft_si_payment_select_end_date_details(transfer_data)
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

    def enter_neft_si_payment_select_end_date_details(self, transfer_data):
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

    def _missing_neft_si_review_values(self, transfer_data, review_text):
        missing_values = super()._missing_neft_si_review_values(
            transfer_data,
            review_text,
        )

        end_date_values = tuple(self._date_review_variants(transfer_data["end_date"]))
        if not any(
            self._normalize_text(value) in review_text for value in end_date_values
        ):
            missing_values.append(end_date_values)

        return missing_values

    def _wait_for_end_date_field(self, timeout: float = 30):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()
            error_match = self.TRANSFER_ERROR_PATTERN.search(body_text)

            if error_match and "select end date" not in body_text.lower():
                raise AssertionError(
                    "End-date SI field failed to load: "
                    f"{error_match.group(0)}\n\nPage text:\n{body_text}"
                )

            if self._find_end_date_field_optional(timeout=1):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for Select end date field after choosing "
            "Standing instruction Schedule as Select end date.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _enter_end_date(self, end_date: str):
        end_date_field = self._find_end_date_field()
        self._dismiss_open_date_picker()
        self._type_date_value(end_date_field, end_date)

        try:
            end_date_field.press("Tab")
        except Exception:
            pass

        self._assert_any_value_visible(
            self._date_review_variants(end_date),
            "selected End Date",
        )

    def _dismiss_open_date_picker(self):
        try:
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(300)
        except Exception:
            pass

    def _type_date_value(self, field, date_value: str):
        for value in self._date_input_variants(date_value):
            self._dismiss_open_date_picker()

            try:
                field.click(timeout=10000)
                field.press("Control+A")
                field.press("Backspace")

                try:
                    field.press_sequentially(value, delay=75)
                except AttributeError:
                    field.type(value, delay=75)

                field.press("Tab")
                self.page.wait_for_timeout(1500)

                if self._date_field_has_expected_value(field, date_value):
                    return
            except Exception:
                continue

        self._force_set_date_value(field, date_value)

        if self._date_field_has_expected_value(field, date_value):
            return

        raise AssertionError(
            f"Could not enter date value {date_value!r} into End date field.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _date_field_has_expected_value(self, field, date_value: str):
        try:
            actual_value = field.input_value(timeout=1000)
        except Exception:
            return False

        normalized_actual = self._normalize_text(actual_value)
        return any(
            self._normalize_text(value) in normalized_actual
            for value in self._date_review_variants(date_value)
        )

    def _force_set_date_value(self, field, date_value: str):
        display_value = self._date_input_variants(date_value)[0]
        iso_value = self._date_iso_value(date_value) or display_value

        field.evaluate(
            """
            (input, values) => {
                const component = input.closest("oj-input-date");

                input.value = values.display;
                input.setAttribute("value", values.display);
                input.dispatchEvent(
                    new InputEvent("input", {
                        bubbles: true,
                        inputType: "insertText",
                        data: values.display
                    })
                );
                input.dispatchEvent(new Event("change", { bubbles: true }));
                input.dispatchEvent(new Event("blur", { bubbles: true }));

                if (component) {
                    if (component.setProperty) {
                        component.setProperty("value", values.iso);
                    }

                    component.value = values.iso;
                    component.classList.remove("oj-has-no-value");
                    component.classList.add("oj-has-value");
                    component.dispatchEvent(
                        new CustomEvent("valueChanged", {
                            bubbles: true,
                            detail: {
                                value: values.iso,
                                previousValue: null,
                                updatedFrom: "external"
                            }
                        })
                    );
                    component.dispatchEvent(new Event("change", { bubbles: true }));
                }
            }
            """,
            {"display": display_value, "iso": iso_value},
        )
        self.page.wait_for_timeout(1000)

    def _date_input_variants(self, date_value: str):
        variants = []
        match = re.fullmatch(
            r"\s*(\d{1,2})[-/\s]([A-Za-z]{3,})[-/\s](\d{4})\s*",
            date_value,
        )

        if match:
            day, month, year = match.groups()
            month_number = self._month_number(month)

            if month_number:
                variants.append(f"{day.zfill(2)}/{month_number}/{year}")

        variants.append(date_value)
        return list(dict.fromkeys(variants))

    def _date_iso_value(self, date_value: str):
        match = re.fullmatch(
            r"\s*(\d{1,2})[-/\s]([A-Za-z]{3,})[-/\s](\d{4})\s*",
            date_value,
        )

        if not match:
            return None

        day, month, year = match.groups()
        month_number = self._month_number(month)

        if not month_number:
            return None

        return f"{year}-{month_number}-{day.zfill(2)}"

    def _find_end_date_field(self):
        field = self._find_end_date_field_optional(timeout=30)

        if field:
            return field

        raise AssertionError(
            "Could not find Select end date field.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _find_end_date_field_optional(self, timeout: float = 1):
        label = re.compile(r"(?:Select\s+)?End\s+date|End\s+Date", re.I)

        field = self._find_visible_field_optional(
            [
                lambda frame: frame.get_by_role("textbox", name=label),
                lambda frame: frame.locator(
                    'input[aria-label*="End Date" i], '
                    'input[aria-label*="Select end date" i], '
                    'input[placeholder*="End Date" i], '
                    'input[placeholder*="Select end date" i], '
                    'input:not([type="radio"]):not([type="checkbox"])'
                    ':not([type="hidden"])[id*="end" i][id*="date" i], '
                    'input:not([type="radio"]):not([type="checkbox"])'
                    ':not([type="hidden"])[name*="end" i][name*="date" i]'
                ),
                lambda frame: self._nearby_field_candidate(frame, label),
            ],
            timeout=timeout,
        )

        if field and self._is_text_date_field(field):
            return field

        return self._find_second_visible_date_field(timeout=timeout)

    @staticmethod
    def _is_text_date_field(field):
        try:
            input_type = (field.get_attribute("type") or "").lower()
        except Exception:
            return False

        return input_type not in ("hidden", "radio", "checkbox")

    def _find_second_visible_date_field(self, timeout: float = 1):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                date_fields = frame.locator(
                    "oj-input-date input, "
                    'input[class*="inputdatetime" i], '
                    'input[id*="date" i], input[name*="date" i]'
                )
                visible_fields = []

                try:
                    count = date_fields.count()
                except Exception:
                    continue

                for index in range(count):
                    field = date_fields.nth(index)

                    try:
                        input_type = (field.get_attribute("type") or "").lower()
                        if input_type in ("hidden", "radio", "checkbox"):
                            continue

                        if field.is_visible() and field.is_enabled():
                            visible_fields.append(field)
                    except Exception:
                        continue

                for field in visible_fields:
                    try:
                        if not field.input_value(timeout=500).strip():
                            return field
                    except Exception:
                        continue

                if len(visible_fields) >= 2:
                    return visible_fields[-1]

            self.page.wait_for_timeout(200)

        return None

    def _save_debug_artifacts(self) -> Path:
        artifact_dir = (
            Path("artifacts")
            / f"neft_si_payment_select_end_date_{time.strftime('%Y%m%d_%H%M%S')}"
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
