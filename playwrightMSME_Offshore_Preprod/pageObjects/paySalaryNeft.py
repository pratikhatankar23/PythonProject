import re
import time
from pathlib import Path

from pageObjects.paySalaryInternalBene import PaySalaryInternalBenePage


class PaySalaryNeftPage(PaySalaryInternalBenePage):
    def pay_salary_neft(self, salary_data):
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

    def enter_pay_employee_details(self, salary_data):
        self._select_employee(salary_data["employeeName"])
        self._select_salary_transfer_from_account(salary_data["fromAccount"])

        amount = self._find_transfer_amount_field()
        self._type_like_user(amount, salary_data["amount"], verify_value=False)

        self._select_salary_transfer_type(salary_data["transferType"])

        remarks = self._find_remarks_field()
        self._type_like_user(remarks, salary_data["remarks"])

        self._click_action(
            re.compile(r"^\s*Proceed\s*$", re.I),
            "Proceed button",
            value_fragments=("Proceed",),
        )
        self._wait_for_transaction_summary_screen(timeout=45)

    def verify_transaction_summary(self, salary_data):
        deadline = time.monotonic() + 30
        missing_values = []
        summary_text = ""

        while time.monotonic() < deadline:
            summary_text = self._normalized_body_text()
            missing_values = self._missing_transaction_summary_values(
                salary_data,
                summary_text,
            )

            if (
                not missing_values
                and self._employee_details_present()
                and self._ifsc_code_present()
            ):
                return

            self.page.wait_for_timeout(500)

        summary_text = self._normalized_body_text()
        missing_values = self._missing_transaction_summary_values(
            salary_data,
            summary_text,
        )

        if not self._employee_details_present():
            missing_values.append(("Employee Details with a value",))

        if not self._ifsc_code_present():
            missing_values.append(("IFSC Code with a value",))

        if missing_values:
            raise AssertionError(
                "Transaction Summary screen is missing expected NEFT salary payment "
                f"value(s): {missing_values}\n\nSummary text:\n{summary_text}"
            )

    def _select_salary_transfer_type(self, transfer_type: str):
        try:
            self._select_radio_option(
                transfer_type,
                "Transfer type",
            )
        except AssertionError as radio_error:
            transfer_type_field = self._find_transfer_type_field_optional(timeout=5)

            if not transfer_type_field:
                if self._transfer_type_visible(transfer_type):
                    return

                raise radio_error

            self._select_dropdown_option(
                transfer_type_field,
                transfer_type,
                "Transfer Type dropdown",
                option_text=transfer_type,
                choose_first_filtered=False,
                allow_keyboard_fallback=False,
            )

        self._assert_value_visible(transfer_type, "selected Transfer Type")

    def _find_transfer_type_field_optional(self, timeout: float = 1):
        label = re.compile(r"Transfer\s+Type", re.I)

        return self._find_visible_field_optional(
            [
                lambda frame: frame.get_by_label(label),
                lambda frame: frame.get_by_placeholder(label),
                lambda frame: frame.get_by_role("combobox", name=label),
                lambda frame: frame.get_by_role("textbox", name=label),
                lambda frame: frame.locator(
                    'input[aria-label*="Transfer Type" i], '
                    'input[placeholder*="Transfer Type" i], '
                    'input[id*="transfer" i][id*="type" i], '
                    'input[name*="transfer" i][name*="type" i], '
                    'input[id*="network" i], input[name*="network" i], '
                    '[role="combobox"][aria-label*="Transfer Type" i]'
                ),
                lambda frame: self._nearby_field_candidate(frame, label),
            ],
            timeout=timeout,
        )

    def _missing_transaction_summary_values(self, salary_data, summary_text):
        expected_value_groups = [
            ("Transfer From",),
            (salary_data["fromAccount"],),
            ("Transfer Amount", "Amount"),
            tuple(self._amount_review_variants(salary_data["amount"])),
            ("Transfer Type",),
            (salary_data["transferType"],),
        ]

        if salary_data.get("remarks"):
            expected_value_groups.extend(
                [
                    ("Remarks", "Remark"),
                    (salary_data["remarks"],),
                ]
            )

        return [
            values
            for values in expected_value_groups
            if not any(
                self._normalize_text(value) in summary_text for value in values if value
            )
        ]

    def _ifsc_code_present(self):
        label_pattern = re.compile(r"IFSC\s+Code", re.I)

        for frame in self.page.frames:
            labels = frame.locator("label, span, div, td, th, oj-label").filter(
                has_text=label_pattern
            )

            try:
                label_count = labels.count()
            except Exception:
                continue

            for index in range(label_count):
                label = labels.nth(index)

                try:
                    if not label.is_visible(timeout=300):
                        continue
                except Exception:
                    continue

                for xpath in (
                    "xpath=ancestor::tr[1]",
                    "xpath=ancestor::*[contains(concat(' ', normalize-space(@class), ' '), ' row ')][1]",
                    "xpath=ancestor::*[contains(concat(' ', normalize-space(@class), ' '), ' oj-flex ')][1]",
                    "xpath=ancestor::*[self::div][2]",
                ):
                    try:
                        scope_text = label.locator(xpath).inner_text(timeout=300)
                    except Exception:
                        continue

                    if self._has_ifsc_code_value(scope_text):
                        return True

        return bool(
            re.search(
                r"ifsc\s+code\s+[a-z]{4}0[a-z0-9]{6}",
                self._normalized_body_text(),
                re.I,
            )
        )

    def _has_ifsc_code_value(self, text: str):
        normalized = self._normalize_text(text)

        if not normalized:
            return False

        value_text = re.sub(r"(ifsc\s+code|:|-)", " ", normalized, flags=re.I).strip()

        return bool(re.search(r"[a-z]{4}0[a-z0-9]{6}", value_text, re.I))

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

    def _transfer_type_visible(self, transfer_type: str):
        return self._normalize_text(transfer_type) in self._normalized_body_text()

    def _save_debug_artifacts(self) -> Path:
        artifact_dir = Path("artifacts") / f"pay_salary_neft_{time.strftime('%Y%m%d_%H%M%S')}"
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
