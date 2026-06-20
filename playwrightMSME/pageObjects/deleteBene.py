import re
import time
from pathlib import Path

from playwright.sync_api import Page

from pageObjects.addYesBankBene import AddYesBankBenePage


class DeleteBenePage(AddYesBankBenePage):
    NO_RECORDS_PATTERN = re.compile(
        r"(no\s+records?\s+found|no\s+beneficiar(?:y|ies)\s+found|"
        r"no\s+payees?\s+found|no\s+results?\s+found|no\s+data\s+found)",
        re.I,
    )
    CONFIRM_AND_PROCEED_PATTERN = re.compile(
        r"^\s*Confirm\s*(?:and|&)\s*Proceed\s*$",
        re.I,
    )
    DELETE_SUCCESS_PATTERN = re.compile(
        r"(Beneficiary\s+Deleted\s+Successfully|"
        r"Beneficiary\s+deleted\s+successfully|"
        r"beneficiary\s+has\s+been\s+deleted|"
        r"successfully\s+deleted|"
        r"payee\s+deleted)",
        re.I,
    )

    def __init__(self, page: Page):
        super().__init__(page)

    def delete_beneficiary(self, delete_data):
        try:
            self._handle_post_login_popups()
            self.navigate_to_manage_beneficiary(delete_data["bene_type"])
            self.delete_first_matching_beneficiary(delete_data["payeename"])
            self.confirm_delete_popup(delete_data["payeename"])
            self.enter_otp_and_submit(delete_data["otp"])
            self.assert_beneficiary_deleted()
        except AssertionError as exc:
            artifact_dir = self._save_debug_artifacts()
            raise AssertionError(
                f"{exc}\n\nDebug artifacts saved to: {artifact_dir.resolve()}"
            ) from None

    def navigate_to_manage_beneficiary(self, bene_type: str):
        self._hover_menu_item("Payments")
        self._hover_menu_item("Manage Beneficiary")
        self._click_leaf_menu_item("Manage Beneficiary")
        self._wait_for_manage_beneficiary_page()
        self._select_beneficiary_type(bene_type)
        self._wait_for_beneficiary_list_ready()

    def delete_first_matching_beneficiary(self, payee_name: str):
        self._search_beneficiary(payee_name)

        if self._has_no_records_message():
            raise AssertionError(
                f"No beneficiary records found after searching for {payee_name!r}."
            )

        delete_action = self._find_matching_delete_action(payee_name, timeout=30)
        if not delete_action:
            raise AssertionError(
                f"Could not find a beneficiary nickname containing {payee_name!r}.\n"
                f"{self._page_snapshot()}\n\n{self._beneficiary_snapshot()}"
            )

        try:
            delete_action.click(timeout=10000)
        except Exception:
            delete_action.evaluate("element => element.click()")

        self.page.wait_for_timeout(1000)

    def confirm_delete_popup(self, payee_name: str):
        dialog_text = self._wait_for_delete_confirmation_text(payee_name)

        if self._normalize_text(payee_name).lower() not in dialog_text.lower():
            raise AssertionError(
                f"Delete confirmation popup did not contain {payee_name!r}.\n"
                f"Popup text:\n{dialog_text}"
            )

        self._click_action(
            self.CONFIRM_AND_PROCEED_PATTERN,
            "Confirm and Proceed button on delete confirmation popup",
            value_fragments=("Confirm", "Proceed"),
            timeout=30,
        )

    def enter_otp_and_submit(self, otp: str):
        self._fill_otp(otp)
        self._click_action(
            self.CONFIRM_AND_PROCEED_PATTERN,
            "Confirm and Proceed button on delete OTP screen",
            value_fragments=("Confirm", "Proceed"),
            timeout=30,
        )

    def assert_beneficiary_deleted(self):
        self._wait_for_page_text(self.DELETE_SUCCESS_PATTERN, timeout=45)

    def _select_beneficiary_type(self, bene_type: str):
        expected_type = self._normalize_text(bene_type)

        if expected_type.lower() not in ("accounts", "beneficiary groups"):
            raise AssertionError(
                "Unsupported bene_type. Use 'Accounts' or 'Beneficiary Groups'."
            )

        if expected_type.lower() == "accounts":
            self._wait_for_page_text(re.compile(r"\bAccounts\b", re.I), timeout=30)
            return

        label_pattern = re.compile(r"^\s*Beneficiary\s+Groups\s*$", re.I)
        type_option = self._find_beneficiary_type_option(label_pattern)

        try:
            type_option.click(timeout=10000)
        except Exception:
            type_option.evaluate("element => element.click()")

        self.page.wait_for_timeout(1000)

    def _find_beneficiary_type_option(self, label_pattern):
        deadline = time.monotonic() + 30

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                option = self._visible_enabled_first(
                    [
                        frame.get_by_role("radio", name=label_pattern),
                        frame.get_by_role("tab", name=label_pattern),
                        frame.get_by_role("button", name=label_pattern),
                        frame.locator("label").filter(has_text=label_pattern),
                        frame.locator("span").filter(has_text=label_pattern),
                        frame.locator("div").filter(has_text=label_pattern),
                    ]
                )

                if option:
                    return option

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Could not find Beneficiary Type option.\n"
            f"{self._page_snapshot()}\n\n{self._action_snapshot()}"
        )

    def _click_leaf_menu_item(self, label: str, timeout: float = 30):
        label_pattern = re.compile(rf"^\s*{re.escape(label)}\s*$", re.I)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                menu_item = self._visible_enabled_first(
                    [
                        frame.locator("li.level-1 span").filter(has_text=label_pattern),
                        frame.locator("li.level-1 div.text-css1").filter(
                            has_text=label_pattern
                        ),
                        frame.locator("ul#innermenufield li span").filter(
                            has_text=label_pattern
                        ),
                    ]
                )

                if not menu_item:
                    continue

                try:
                    menu_item.click(timeout=10000)
                except Exception:
                    menu_item.evaluate("element => element.click()")

                try:
                    self.page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass

                self.page.wait_for_timeout(1000)
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            f"Could not find {label} submenu item.\n"
            f"{self._page_snapshot()}\n\n{self._action_snapshot()}"
        )

    def _wait_for_manage_beneficiary_page(self, timeout: float = 45):
        screen_pattern = re.compile(
            r"(Beneficiaries|Beneficiary\s+Groups|payee[-\s]*list|Nickname)",
            re.I,
        )
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            current_url = self.page.url.lower()
            body_text = self._normalized_body_text()

            if (
                "payee" in current_url
                or "beneficiar" in current_url
                or screen_pattern.search(body_text)
            ):
                if "current account" not in body_text.lower() or "nickname" in body_text.lower():
                    return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for Manage Beneficiary screen.\n"
            f"{self._page_snapshot()}"
        )

    def _wait_for_beneficiary_list_ready(self, timeout: float = 30):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()

            if self.NO_RECORDS_PATTERN.search(body_text):
                return

            if self._has_any_beneficiary_record():
                return

            self.page.wait_for_timeout(500)

    def _has_no_records_message(self):
        return bool(self.NO_RECORDS_PATTERN.search(self._normalized_body_text()))

    def _has_any_beneficiary_record(self):
        for frame in self.page.frames:
            if self._visible_first(self._record_locators(frame)):
                return True

        return False

    def _find_matching_delete_action(self, payee_name: str, timeout: float = 30):
        payee_pattern = re.compile(re.escape(payee_name), re.I)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                row = self._find_matching_record_row(frame, payee_pattern)

                if not row:
                    continue

                try:
                    row.hover(timeout=5000)
                except Exception:
                    pass

                delete_action = self._find_delete_action_in_row(row)

                if delete_action:
                    return delete_action

                self._open_row_more_actions(row)
                delete_action = self._find_delete_action_in_row(row)

                if delete_action:
                    return delete_action

                delete_action = self._find_visible_delete_action(frame)

                if delete_action:
                    return delete_action

            self.page.wait_for_timeout(500)

        return None

    def _find_matching_record_row(self, frame, payee_pattern):
        for rows in self._record_locators(frame):
            row = self._visible_first([rows.filter(has_text=payee_pattern)])

            if row:
                return row

        return None

    def _record_locators(self, frame):
        return [
            frame.locator("tr"),
            frame.locator("li"),
            frame.locator("[role='row']"),
            frame.locator(".oj-listview-item"),
            frame.locator(".oj-listview-item-element"),
            frame.locator("oj-list-item-layout"),
            frame.locator("[data-oj-context]"),
            frame.locator("div[class*='payee' i]"),
            frame.locator("div[class*='beneficiary' i]"),
            frame.locator("div[class*='list' i]"),
            frame.locator("div[class*='card' i]"),
        ]

    def _find_delete_action_in_row(self, row):
        delete_pattern = re.compile(r"(delete|remove)", re.I)
        return self._visible_enabled_first(
            [
                row.get_by_role("button", name=delete_pattern),
                row.get_by_role("link", name=delete_pattern),
                row.locator("button").filter(has_text=delete_pattern),
                row.locator("a").filter(has_text=delete_pattern),
                row.locator("[role='button']").filter(has_text=delete_pattern),
                row.locator("[aria-label*='delete' i]"),
                row.locator("[title*='delete' i]"),
                row.locator("[alt*='delete' i]"),
                row.locator("[id*='delete' i]"),
                row.locator("[class*='delete' i]"),
                row.locator("[class*='trash' i]"),
                row.locator("[class*='bin' i]"),
            ]
        )

    def _find_visible_delete_action(self, frame):
        delete_pattern = re.compile(r"(delete|remove)", re.I)
        return self._visible_enabled_first(
            [
                frame.get_by_role("button", name=delete_pattern),
                frame.get_by_role("link", name=delete_pattern),
                frame.locator("button").filter(has_text=delete_pattern),
                frame.locator("a").filter(has_text=delete_pattern),
                frame.locator("[role='button']").filter(has_text=delete_pattern),
                frame.locator("[aria-label*='delete' i]"),
                frame.locator("[title*='delete' i]"),
                frame.locator("[alt*='delete' i]"),
                frame.locator("[id*='delete' i]"),
                frame.locator("[class*='delete' i]"),
                frame.locator("[class*='trash' i]"),
                frame.locator("[class*='bin' i]"),
            ]
        )

    def _open_row_more_actions(self, row):
        more_pattern = re.compile(r"(more|actions?|options?|menu)", re.I)
        more_action = self._visible_enabled_first(
            [
                row.get_by_role("button", name=more_pattern),
                row.get_by_role("link", name=more_pattern),
                row.locator("[aria-label*='more' i]"),
                row.locator("[title*='more' i]"),
                row.locator("[aria-label*='action' i]"),
                row.locator("[title*='action' i]"),
                row.locator("[class*='more' i]"),
                row.locator("[class*='menu' i]"),
                row.locator("[class*='ellipsis' i]"),
            ]
        )

        if not more_action:
            return

        try:
            more_action.click(timeout=5000)
            self.page.wait_for_timeout(500)
        except Exception:
            pass

    def _search_beneficiary(self, payee_name: str):
        search = self._find_search_field()
        search.click(timeout=10000)
        search.press("Control+A")
        search.press("Backspace")

        try:
            search.press_sequentially(payee_name, delay=75)
        except AttributeError:
            search.type(payee_name, delay=75)

        search.press("Enter")
        self._click_search_action_if_visible()
        self.page.wait_for_timeout(2000)

    def _find_search_field(self, timeout: float = 30):
        search_pattern = re.compile(r"search", re.I)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                search = self._first_beneficiary_search_candidate(
                    [
                        frame.locator("payment-search-box input"),
                        frame.locator("obdx-component-payee-list input"),
                        frame.locator("#obdx-component-payee-list input"),
                        frame.locator(".payment-search-box-container input"),
                        frame.locator('input[placeholder*="beneficiar" i]'),
                        frame.locator('input[aria-label*="beneficiar" i]'),
                        frame.locator('input[placeholder*="payee" i]'),
                        frame.locator('input[aria-label*="payee" i]'),
                        frame.locator('input[placeholder*="nickname" i]'),
                        frame.locator('input[aria-label*="nickname" i]'),
                        frame.get_by_role("searchbox"),
                        frame.get_by_role("textbox", name=search_pattern),
                        frame.get_by_placeholder(search_pattern),
                        frame.locator('input[type="search"]'),
                        frame.locator('input[aria-label*="search" i]'),
                        frame.locator('input[placeholder*="search" i]'),
                        frame.locator('input[id*="search" i]'),
                        frame.locator('input[name*="search" i]'),
                    ]
                )

                if search:
                    return search

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Could not find Beneficiaries search field.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _first_beneficiary_search_candidate(self, locators):
        for locator in locators:
            try:
                for index in range(locator.count()):
                    candidate = locator.nth(index)

                    if not candidate.is_visible() or not candidate.is_enabled():
                        continue

                    if self._is_beneficiary_search_field(candidate):
                        return candidate
            except Exception:
                continue

        return None

    def _is_beneficiary_search_field(self, field):
        try:
            attrs = field.evaluate(
                """
                e => {
                  const container = e.closest(
                    'payment-search-box, obdx-component-payee-list, '
                    + '#obdx-component-payee-list, .payment-search-box-container, '
                    + '[class*="payee"], [class*="beneficiary"]'
                  );

                  return {
                    type: (e.getAttribute('type') || '').toLowerCase(),
                    id: e.id || '',
                    name: e.getAttribute('name') || '',
                    placeholder: e.getAttribute('placeholder') || '',
                    aria: e.getAttribute('aria-label') || '',
                    role: e.getAttribute('role') || '',
                    containerText: container
                      ? (container.innerText || container.textContent || '')
                      : ''
                  };
                }
                """
            )
        except Exception:
            return False

        field_text = self._normalize_text(
            " ".join(
                str(attrs.get(key) or "")
                for key in ("type", "id", "name", "placeholder", "aria", "role")
            )
        )
        container_text = self._normalize_text(attrs.get("containerText") or "")
        combined_text = f"{field_text} {container_text}".lower()

        excluded_terms = (
            "what are you looking for today",
            "payeename|input",
            "oj-searchselect-filter-payeename",
        )

        if any(term in combined_text for term in excluded_terms):
            return False

        return bool(
            re.search(r"(search|filter|beneficiar|payee|nickname)", combined_text, re.I)
        )

    def _click_search_action_if_visible(self):
        search_pattern = re.compile(r"^\s*search\s*$", re.I)

        for frame in self.page.frames:
            action = self._visible_enabled_first(
                [
                    frame.get_by_role("button", name=search_pattern),
                    frame.get_by_role("link", name=search_pattern),
                    frame.locator("[aria-label*='search' i]"),
                    frame.locator("[title*='search' i]"),
                    frame.locator("[class*='search' i]"),
                ]
            )

            if action:
                try:
                    action.click(timeout=3000)
                    return
                except Exception:
                    continue

    def _wait_for_delete_confirmation_text(self, payee_name: str, timeout: float = 30):
        payee_pattern = re.compile(re.escape(payee_name), re.I)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            dialog_text = self._confirmation_dialog_text()

            if dialog_text and payee_pattern.search(dialog_text):
                return dialog_text

            self.page.wait_for_timeout(500)

        raise AssertionError(
            f"Timed out waiting for delete confirmation popup containing {payee_name!r}.\n"
            f"{self._page_snapshot()}\n\n{self._action_snapshot()}"
        )

    def _confirmation_dialog_text(self):
        for frame in self.page.frames:
            dialog = self._visible_first(
                [
                    frame.get_by_role("dialog"),
                    frame.locator("[role='alertdialog']"),
                    frame.locator(".oj-dialog"),
                    frame.locator(".oj-popup"),
                    frame.locator("[class*='popup' i]"),
                    frame.locator("[class*='modal' i]"),
                ]
            )

            if dialog:
                try:
                    return self._normalize_text(dialog.inner_text(timeout=1000))
                except Exception:
                    continue

        return ""

    def _beneficiary_snapshot(self) -> str:
        rows = []
        script = """
        els => els.map((e, idx) => ({
          idx,
          tag: e.tagName.toLowerCase(),
          id: e.id || "",
          role: e.getAttribute("role") || "",
          classes: e.className || "",
          text: (e.innerText || e.textContent || "").trim().replace(/\\s+/g, " "),
          visible: !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length)
        }))
        """
        selector = (
            "tr, li, [role='row'], .oj-listview-item, .oj-listview-item-element, "
            "oj-list-item-layout, [data-oj-context], div[class*='payee' i], "
            "div[class*='beneficiary' i], div[class*='list' i], div[class*='card' i]"
        )

        for frame_index, frame in enumerate(self.page.frames):
            try:
                records = frame.locator(selector).evaluate_all(script)
            except Exception as exc:
                rows.append(f"frame={frame_index} url={frame.url} unavailable: {exc}")
                continue

            for record in records:
                rows.append(
                    "frame={frame} url={url} idx={idx} tag={tag} id={id} "
                    "role={role} classes={classes} visible={visible} text={text}".format(
                        frame=frame_index,
                        url=frame.url,
                        **record,
                    )
                )

        return "\n".join(rows) or "No beneficiary-like record elements were found."

    def _save_debug_artifacts(self) -> Path:
        artifact_dir = Path("artifacts") / f"delete_bene_{time.strftime('%Y%m%d_%H%M%S')}"
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
                    "BENEFICIARIES",
                    self._beneficiary_snapshot(),
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
