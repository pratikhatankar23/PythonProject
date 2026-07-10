import re
import time
from pathlib import Path

from playwright.sync_api import Page

from pageObjects.neftRegPayeeOnetime import NeftRegPayeeOnetimePage


class DeleteSIPage(NeftRegPayeeOnetimePage):
    STANDING_INSTRUCTIONS_PATTERN = re.compile(
        r"^\s*Standing\s+Instructions\s*$",
        re.I,
    )
    NO_DATA_PATTERN = re.compile(
        r"(no\s+data\s+to\s+display|no\s+records?\s+found|"
        r"no\s+results?\s+found|no\s+standing\s+instructions?\s+found)",
        re.I,
    )
    DELETE_CONFIRMATION_PATTERN = re.compile(
        r"Are\s+you\s+sure\s+you\s+want\s+to\s+delete\s+this\s+standing\s+Instructions\?",
        re.I,
    )
    DELETE_SUCCESS_PATTERN = re.compile(
        r"Standing\s+instruction\s+deleted\s+successfully",
        re.I,
    )

    def __init__(self, page: Page):
        super().__init__(page)

    def delete_standing_instruction(self, delete_data):
        try:
            self._handle_post_login_popups()
            self.navigate_to_standing_instructions()
            self.search_standing_instruction(delete_data["bene_name"])
            self.delete_first_displayed_standing_instruction()
            self.confirm_delete()
            self.confirm_otp_if_displayed(delete_data["otp"])
            self.assert_standing_instruction_deleted()
        except Exception as exc:
            artifact_dir = self._save_debug_artifacts()
            error_message = str(exc)
            if not isinstance(exc, AssertionError):
                error_message = f"{type(exc).__name__}: {exc}"

            raise AssertionError(
                f"{error_message}\n\nDebug artifacts saved to: {artifact_dir.resolve()}"
            ) from None

    def navigate_to_standing_instructions(self):
        self._hover_menu_item("Payments")
        self._hover_menu_item("Single Payments")
        self._click_standing_instructions_menu_item()
        self._wait_for_standing_instructions_screen(timeout=45)
        self._dismiss_open_navigation_menu()

    def search_standing_instruction(self, bene_name: str):
        search = self._find_search_si_field()

        try:
            search.click(timeout=10000)
        except Exception:
            self._dismiss_open_navigation_menu()
            try:
                search.click(timeout=5000)
            except Exception:
                search.click(timeout=5000, force=True)

        search.press("Control+A")
        search.press("Backspace")

        try:
            search.press_sequentially(bene_name, delay=75)
        except AttributeError:
            search.type(bene_name, delay=75)

        search.press("Enter")
        self._click_search_action_if_visible()
        self._wait_for_search_results(bene_name, timeout=30)

    def delete_first_displayed_standing_instruction(self):
        if self._has_no_data_message():
            raise AssertionError("No data to display after searching Standing Instructions.")

        delete_action = self._find_first_delete_action(timeout=30)
        if not delete_action:
            raise AssertionError(
                "Could not find delete/bin icon for the first displayed Standing "
                f"Instruction record.\n{self._page_snapshot()}\n\n"
                f"{self._standing_instruction_snapshot()}"
            )

        try:
            delete_action.click(timeout=10000)
        except Exception:
            delete_action.evaluate("element => element.click()")

        self.page.wait_for_timeout(1000)

    def confirm_delete(self):
        confirmation_text = self._wait_for_delete_confirmation_text(timeout=30)

        if not self.DELETE_CONFIRMATION_PATTERN.search(confirmation_text):
            raise AssertionError(
                "Delete confirmation popup text was not as expected.\n"
                f"Popup text:\n{confirmation_text}"
            )

        self._click_action(
            re.compile(r"^\s*Delete\s*$", re.I),
            "Delete button on Standing Instruction confirmation popup",
            value_fragments=("Delete",),
            timeout=30,
        )

    def confirm_otp_if_displayed(self, otp: str):
        if self._success_visible(timeout=5):
            return

        if not self._otp_visible(timeout=10):
            if self._success_visible(timeout=10):
                return

            return

        self._fill_otp(otp)
        self._click_action(
            self.CONFIRM_AND_PROCEED_PATTERN,
            "Confirm and Proceed button on delete SI OTP screen",
            value_fragments=("Confirm", "Proceed"),
            timeout=30,
        )

    def assert_standing_instruction_deleted(self):
        deadline = time.monotonic() + 45

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()

            if self.DELETE_SUCCESS_PATTERN.search(body_text):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for Standing instruction deleted successfully "
            f"confirmation.\n{self._page_snapshot()}"
        )

    def _click_standing_instructions_menu_item(self, timeout: float = 30):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                menu_item = self._visible_enabled_first(
                    [
                        frame.locator("li.level-1 span").filter(
                            has_text=self.STANDING_INSTRUCTIONS_PATTERN
                        ),
                        frame.locator("li.level-1 div.text-css1").filter(
                            has_text=self.STANDING_INSTRUCTIONS_PATTERN
                        ),
                        frame.locator("ul.innersubmenucssnew li span").filter(
                            has_text=self.STANDING_INSTRUCTIONS_PATTERN
                        ),
                        frame.locator("span").filter(
                            has_text=self.STANDING_INSTRUCTIONS_PATTERN
                        ),
                        frame.locator("div.text-css1").filter(
                            has_text=self.STANDING_INSTRUCTIONS_PATTERN
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
            "Could not find Standing Instructions submenu item.\n"
            f"{self._page_snapshot()}\n\n{self._action_snapshot()}"
        )

    def _wait_for_standing_instructions_screen(self, timeout: float = 45):
        screen_pattern = re.compile(
            r"(Standing\s+Instructions|Search\s+SI|Beneficiary|Frequency|Start\s+Date)",
            re.I,
        )
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()

            if screen_pattern.search(body_text):
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for Standing Instructions screen.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _dismiss_open_navigation_menu(self):
        for _ in range(3):
            try:
                self.page.keyboard.press("Escape")
            except Exception:
                pass

            try:
                viewport = self.page.viewport_size or {"width": 1366, "height": 768}
                x_position = max(viewport["width"] - 25, 1)
                y_position = min(max(viewport["height"] // 2, 240), viewport["height"] - 25)
                self.page.mouse.move(x_position, y_position)
            except Exception:
                pass

            self.page.wait_for_timeout(500)

    def _find_search_si_field(self, timeout: float = 30):
        search_pattern = re.compile(r"(Search\s+SI|Search|Beneficiary)", re.I)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                search = self._visible_enabled_first(
                    [
                        frame.get_by_role("searchbox", name=search_pattern),
                        frame.get_by_role("textbox", name=search_pattern),
                        frame.get_by_placeholder(search_pattern),
                        frame.locator('input[aria-label*="Search SI" i]'),
                        frame.locator('input[placeholder*="Search SI" i]'),
                        frame.locator('input[aria-label*="Search" i]'),
                        frame.locator('input[placeholder*="Search" i]'),
                        frame.locator('input[id*="search" i]'),
                        frame.locator('input[name*="search" i]'),
                        frame.locator('input[type="search"]'),
                    ]
                )

                if search and self._is_search_si_field(search):
                    return search

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Could not find Search SI field.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _is_search_si_field(self, field):
        try:
            attrs = field.evaluate(
                """
                e => ({
                  id: e.id || "",
                  name: e.getAttribute("name") || "",
                  placeholder: e.getAttribute("placeholder") || "",
                  aria: e.getAttribute("aria-label") || "",
                  role: e.getAttribute("role") || "",
                  text: (e.closest("payment-search-box, [class*='search' i], form, section, div")
                    || e).innerText || ""
                })
                """
            )
        except Exception:
            return False

        combined_text = self._normalize_text(
            " ".join(str(attrs.get(key) or "") for key in attrs)
        ).lower()

        if "what are you looking for today" in combined_text:
            return False

        return bool(re.search(r"(search|si|standing|beneficiary)", combined_text, re.I))

    def _click_search_action_if_visible(self):
        search_pattern = re.compile(r"^\s*Search\s*$", re.I)

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

            if not action:
                continue

            try:
                action.click(timeout=3000)
                return
            except Exception:
                continue

    def _wait_for_search_results(self, bene_name: str, timeout: float = 30):
        bene_pattern = re.compile(re.escape(bene_name), re.I)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()

            if self.NO_DATA_PATTERN.search(body_text):
                raise AssertionError(
                    f"No data to display after searching for {bene_name!r}."
                )

            if bene_pattern.search(body_text) or self._has_any_si_record():
                return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            f"Timed out waiting for Standing Instruction search result {bene_name!r}.\n"
            f"{self._page_snapshot()}\n\n{self._standing_instruction_snapshot()}"
        )

    def _has_no_data_message(self):
        return bool(self.NO_DATA_PATTERN.search(self._normalized_body_text()))

    def _has_any_si_record(self):
        for frame in self.page.frames:
            if self._visible_first(self._record_locators(frame)):
                return True

        return False

    def _find_first_delete_action(self, timeout: float = 30):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                rows = self._record_locators(frame)

                for rows_locator in rows:
                    try:
                        count = rows_locator.count()
                    except Exception:
                        continue

                    for index in range(count):
                        row = rows_locator.nth(index)

                        try:
                            if not row.is_visible():
                                continue
                        except Exception:
                            continue

                        delete_action = self._find_delete_action_in_scope(row)
                        if delete_action:
                            return delete_action

                        self._open_row_more_actions(row)
                        delete_action = self._find_delete_action_in_scope(row)
                        if delete_action:
                            return delete_action

                delete_action = self._find_delete_action_in_scope(frame)
                if delete_action:
                    return delete_action

            self.page.wait_for_timeout(500)

        return None

    def _record_locators(self, frame):
        return [
            frame.locator("tr"),
            frame.locator("[role='row']"),
            frame.locator(".oj-listview-item"),
            frame.locator(".oj-listview-item-element"),
            frame.locator("oj-list-item-layout"),
            frame.locator("li"),
            frame.locator("div[class*='standing' i]"),
            frame.locator("div[class*='instruction' i]"),
            frame.locator("div[class*='list' i]"),
            frame.locator("div[class*='card' i]"),
        ]

    def _find_delete_action_in_scope(self, scope):
        delete_pattern = re.compile(r"(delete|remove)", re.I)
        return self._visible_enabled_first(
            [
                scope.get_by_role("button", name=delete_pattern),
                scope.get_by_role("link", name=delete_pattern),
                scope.locator("button").filter(has_text=delete_pattern),
                scope.locator("a").filter(has_text=delete_pattern),
                scope.locator("[role='button']").filter(has_text=delete_pattern),
                scope.locator("[aria-label*='delete' i]"),
                scope.locator("[title*='delete' i]"),
                scope.locator("[alt*='delete' i]"),
                scope.locator("[id*='delete' i]"),
                scope.locator("[class*='delete' i]"),
                scope.locator("[class*='trash' i]"),
                scope.locator("[class*='bin' i]"),
                scope.locator("img[src*='delete' i]"),
                scope.locator("img[src*='trash' i]"),
                scope.locator("img[src*='bin' i]"),
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

    def _wait_for_delete_confirmation_text(self, timeout: float = 30):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            dialog_text = self._confirmation_dialog_text()

            if dialog_text and self.DELETE_CONFIRMATION_PATTERN.search(dialog_text):
                return dialog_text

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for delete Standing Instruction confirmation popup.\n"
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

    def _otp_visible(self, timeout: float = 10):
        deadline = time.monotonic() + timeout
        otp_pattern = re.compile(r"(otp|one\s*time|verification|security\s*code)", re.I)

        while time.monotonic() < deadline:
            if otp_pattern.search(self._normalized_body_text()):
                return True

            self.page.wait_for_timeout(500)

        return False

    def _success_visible(self, timeout: float = 5):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if self.DELETE_SUCCESS_PATTERN.search(self._normalized_body_text()):
                return True

            self.page.wait_for_timeout(500)

        return False

    def _standing_instruction_snapshot(self) -> str:
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
            "oj-list-item-layout, div[class*='standing' i], "
            "div[class*='instruction' i], div[class*='list' i], "
            "div[class*='card' i]"
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

        return "\n".join(rows) or "No Standing Instruction-like records were found."

    def _save_debug_artifacts(self) -> Path:
        artifact_dir = Path("artifacts") / f"delete_si_{time.strftime('%Y%m%d_%H%M%S')}"
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
                    "STANDING INSTRUCTIONS",
                    self._standing_instruction_snapshot(),
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
