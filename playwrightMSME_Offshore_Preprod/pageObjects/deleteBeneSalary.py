import re
import time
from pathlib import Path

from playwright.sync_api import Page

from pageObjects.deleteBene import DeleteBenePage


class DeleteBeneSalaryPage(DeleteBenePage):
    NO_RECORDS_PATTERN = re.compile(
        r"(no\s+records?\s+found|no\s+employees?\s+found|"
        r"no\s+results?\s+found|no\s+data\s+found|"
        r"no\s+data\s+to\s+display)",
        re.I,
    )
    DELETE_SUCCESS_PATTERN = re.compile(
        r"(Employee\s+Deleted\s+Successfully|"
        r"Employee\s+deleted\s+successfully|"
        r"employee\s+has\s+been\s+deleted|"
        r"employee\s+deleted|"
        r"successfully\s+deleted|"
        r"has\s+been\s+removed\s+from\s+the\s+employee\s+list\s+successfully|"
        r"removed\s+from\s+the\s+employee\s+list\s+successfully)",
        re.I,
    )

    def __init__(self, page: Page):
        super().__init__(page)

    def delete_salary_beneficiary(self, delete_data):
        employee_name = delete_data["employeeName"]

        try:
            self._handle_post_login_popups()
            self.navigate_to_manage_employee()
            self.delete_first_matching_employee(employee_name)
            self.confirm_delete_popup(employee_name)
            self.enter_otp_and_submit(delete_data["otp"])
            self.assert_employee_deleted()
        except Exception as exc:
            artifact_dir = self._save_debug_artifacts()
            error_message = str(exc)
            if not isinstance(exc, AssertionError):
                error_message = f"{type(exc).__name__}: {exc}"

            raise AssertionError(
                f"{error_message}\n\nDebug artifacts saved to: {artifact_dir.resolve()}"
            ) from None

    def navigate_to_manage_employee(self):
        self._hover_menu_item("Payments")
        self._hover_menu_item("Salary Management")
        self._click_salary_leaf_menu_item("Manage Employee")
        self._wait_for_manage_employees_page(timeout=45)
        self._wait_for_employee_list_ready(timeout=30)

        if self._has_no_records_message():
            raise AssertionError("No employee records found on Manage Employees screen.")

    def delete_first_matching_employee(self, employee_name: str):
        delete_action = self._find_matching_delete_action(employee_name, timeout=5)

        if not delete_action:
            self._search_employee(employee_name)
            self._wait_for_employee_search_result(employee_name, timeout=30)

        if not delete_action and not self._has_no_records_message():
            delete_action = self._find_matching_delete_action(employee_name, timeout=20)

        if not delete_action:
            delete_action = self._find_matching_employee_across_pages(employee_name)

        if not delete_action:
            raise AssertionError(
                "Could not find a delete/bin icon for the first employee record "
                f"after searching for {employee_name!r}.\n"
                f"{self._page_snapshot()}\n\n{self._employee_snapshot()}"
            )

        self._click_employee_delete_action(delete_action)

        self.page.wait_for_timeout(1000)

    def _find_matching_employee_across_pages(self, employee_name: str):
        self._clear_employee_search()
        self._wait_for_employee_list_ready(timeout=20)

        delete_action = self._find_matching_delete_action(employee_name, timeout=5)
        if delete_action:
            return delete_action

        visited_pages = set()
        deadline = time.monotonic() + 45

        while time.monotonic() < deadline:
            page_action, page_label = self._find_next_employee_page_action(visited_pages)

            if not page_action:
                break

            visited_pages.add(page_label)
            self._click_pagination_action(page_action)
            self._wait_for_employee_list_ready(timeout=20)

            delete_action = self._find_matching_delete_action(employee_name, timeout=5)
            if delete_action:
                return delete_action

        return None

    def _clear_employee_search(self):
        search = self._find_employee_search_field()
        search.click(timeout=10000)
        search.press("Control+A")
        search.press("Backspace")
        self._click_employee_search_action(search)
        self.page.wait_for_timeout(1500)

    def _find_next_employee_page_action(self, visited_pages):
        page_pattern = re.compile(r"\bPage\s+\d+\b", re.I)

        for frame in self.page.frames:
            page_links = [
                frame.locator("a[title*='Go To Page' i]"),
                frame.locator("button[title*='Go To Page' i]"),
                frame.locator("[aria-label*='Go To Page' i]"),
                frame.get_by_role("link", name=page_pattern),
                frame.get_by_role("button", name=page_pattern),
            ]

            for locator in page_links:
                try:
                    count = locator.count()
                except Exception:
                    continue

                for index in range(count):
                    candidate = locator.nth(index)

                    try:
                        if not candidate.is_visible(timeout=500):
                            continue
                    except Exception:
                        continue

                    page_label = self._pagination_action_label(candidate)

                    if not page_label or page_label in visited_pages:
                        continue

                    return candidate, page_label

        return None, None

    def _pagination_action_label(self, action) -> str:
        try:
            attrs = action.evaluate(
                """
                e => [
                  e.getAttribute('title') || '',
                  e.getAttribute('aria-label') || '',
                  e.innerText || e.textContent || ''
                ].join(' ')
                """
            )
        except Exception:
            return ""

        label = self._normalize_text(attrs)
        match = re.search(r"Page\s+\d+", label, re.I)

        if match:
            return match.group(0).lower()

        return label.lower()

    def _click_pagination_action(self, action):
        try:
            action.click(timeout=10000, force=True)
        except Exception:
            action.evaluate(
                """
                element => element.dispatchEvent(new MouseEvent(
                  'click',
                  { bubbles: true, cancelable: true, view: window }
                ))
                """
            )

        try:
            self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        self.page.wait_for_timeout(1000)

    def assert_employee_deleted(self):
        self._wait_for_page_text(self.DELETE_SUCCESS_PATTERN, timeout=45)

    def _click_salary_leaf_menu_item(self, label: str, timeout: float = 30):
        label_pattern = re.compile(rf"^\s*{re.escape(label)}s?\s*$", re.I)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                menu_item = self._visible_enabled_first(
                    [
                        frame.locator("li.level-1 span").filter(has_text=label_pattern),
                        frame.locator("li.level-1 div.text-css1").filter(
                            has_text=label_pattern
                        ),
                        frame.locator("ul.innersubmenucssnew li span").filter(
                            has_text=label_pattern
                        ),
                        frame.locator("ul#innermenufield li span").filter(
                            has_text=label_pattern
                        ),
                        frame.locator("span").filter(has_text=label_pattern),
                        frame.locator("div.text-css1").filter(has_text=label_pattern),
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
            f"Could not find {label} submenu item under Salary Management.\n"
            f"{self._page_snapshot()}\n\n{self._action_snapshot()}"
        )

    def _wait_for_manage_employees_page(self, timeout: float = 45):
        screen_pattern = re.compile(
            r"(Manage\s+Employees?|Search\s+Employees?|Employee\s+Name|"
            r"Employee\s+ID|Employee\s+Details)",
            re.I,
        )
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            current_url = self.page.url.lower()
            body_text = self._normalized_body_text()

            if "employee" in current_url or screen_pattern.search(body_text):
                if (
                    self.NO_RECORDS_PATTERN.search(body_text)
                    or self._has_any_employee_record()
                    or self._find_employee_search_field_optional()
                ):
                    return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Timed out waiting for Manage Employees screen.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _wait_for_employee_list_ready(self, timeout: float = 30):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            body_text = self._normalized_body_text()

            if self.NO_RECORDS_PATTERN.search(body_text):
                return

            if self._has_any_employee_record():
                return

            self.page.wait_for_timeout(500)

    def _has_any_employee_record(self):
        for frame in self.page.frames:
            if self._visible_first(self._record_locators(frame)):
                return True

        return False

    def _search_employee(self, employee_name: str):
        search = self._find_employee_search_field()
        search.click(timeout=10000)
        search.press("Control+A")
        search.press("Backspace")

        try:
            search.press_sequentially(employee_name, delay=75)
        except AttributeError:
            search.type(employee_name, delay=75)

        self._click_employee_search_action(search)
        self.page.wait_for_timeout(500)

    def _wait_for_employee_search_result(self, employee_name: str, timeout: float = 30):
        employee_pattern = re.compile(re.escape(employee_name), re.I)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if self._has_no_records_message():
                return

            for frame in self.page.frames:
                row = self._find_matching_record_row(frame, employee_pattern)

                if row:
                    return

            self.page.wait_for_timeout(500)

        raise AssertionError(
            f"Timed out waiting for search results for employee {employee_name!r}.\n"
            f"{self._page_snapshot()}\n\n{self._employee_snapshot()}"
        )

    def _find_employee_search_field(self, timeout: float = 30):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            search = self._find_employee_search_field_optional()

            if search:
                return search

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Could not find Search Employees field.\n"
            f"{self._page_snapshot()}\n\n{self._input_snapshot()}"
        )

    def _find_employee_search_field_optional(self):
        search_pattern = re.compile(r"(Search\s+Employees?|Employee)", re.I)

        for frame in self.page.frames:
            search = self._first_employee_search_candidate(
                [
                    frame.locator("input[placeholder*='Search Employee' i]"),
                    frame.locator("input[aria-label*='Search Employee' i]"),
                    frame.locator("input[placeholder*='employee' i]"),
                    frame.locator("input[aria-label*='employee' i]"),
                    frame.locator("input[id*='employee' i][id*='search' i]"),
                    frame.locator("input[name*='employee' i][name*='search' i]"),
                    frame.locator("search-box input"),
                    frame.locator("payment-search-box input"),
                    frame.locator(".search-box input"),
                    frame.locator(".payment-search-box-container input"),
                    frame.get_by_role("searchbox"),
                    frame.get_by_role("textbox", name=search_pattern),
                    frame.get_by_placeholder(search_pattern),
                    frame.locator("input[type='search']"),
                    frame.locator("input[aria-label*='search' i]"),
                    frame.locator("input[placeholder*='search' i]"),
                    frame.locator("input[id*='search' i]"),
                    frame.locator("input[name*='search' i]"),
                ]
            )

            if search:
                return search

        return None

    def _first_employee_search_candidate(self, locators):
        for locator in locators:
            try:
                for index in range(locator.count()):
                    candidate = locator.nth(index)

                    if not candidate.is_visible() or not candidate.is_enabled():
                        continue

                    if self._is_employee_search_field(candidate):
                        return candidate
            except Exception:
                continue

        return None

    def _is_employee_search_field(self, field):
        try:
            attrs = field.evaluate(
                """
                e => {
                  const container = e.closest(
                    'search-box, payment-search-box, .search-box, '
                    + '.payment-search-box-container, [class*="employee"], '
                    + '[class*="salary"], [class*="search"]'
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

        if "what are you looking for today" in combined_text:
            return False

        return bool(re.search(r"(search|filter|employee)", combined_text, re.I))

    def _click_employee_search_action(self, search_field):
        scoped_search = self._find_search_action_near_field(search_field)

        if scoped_search:
            if self._click_search_action(scoped_search):
                return

        try:
            search_field.press("Enter")
        except Exception:
            pass

    def _click_search_action(self, action) -> bool:
        try:
            action.click(timeout=5000, force=True)
            return True
        except Exception:
            pass

        try:
            action.evaluate(
                """
                element => element.dispatchEvent(new MouseEvent(
                  'click',
                  { bubbles: true, cancelable: true, view: window }
                ))
                """
            )
            return True
        except Exception:
            return False

    def _find_search_action_near_field(self, search_field):
        search_pattern = re.compile(r"^\s*search\s*$", re.I)
        scopes = []
        direct_actions = self._visible_first(
            [
                search_field.locator(
                    "xpath=ancestor::div[contains(concat(' ', normalize-space(@class), ' '), "
                    "' oj-flex-item ')][1]/following-sibling::div[contains(concat(' ', "
                    "normalize-space(@class), ' '), ' search ')][1]//span[contains(concat(' ', "
                    "normalize-space(@class), ' '), ' icon-search ')]"
                ),
                search_field.locator(
                    "xpath=ancestor::div[contains(concat(' ', normalize-space(@class), ' '), "
                    "' oj-flex-item ')][1]/following-sibling::div[contains(concat(' ', "
                    "normalize-space(@class), ' '), ' search ')][1]"
                ),
                search_field.locator(
                    "xpath=ancestor::payment-search-box[1]//span[contains(concat(' ', "
                    "normalize-space(@class), ' '), ' icon-search ')]"
                ),
                search_field.locator(
                    "xpath=ancestor::payment-search-box[1]//div[contains(concat(' ', "
                    "normalize-space(@class), ' '), ' search ')][.//span[contains(concat(' ', "
                    "normalize-space(@class), ' '), ' icon-search ')]]"
                ),
                search_field.locator(
                    "xpath=ancestor::div[contains(concat(' ', normalize-space(@class), ' '), "
                    "' oj-flex ')][1]//span[contains(concat(' ', normalize-space(@class), ' '), "
                    "' icon-search ')]"
                ),
            ]
        )

        if direct_actions:
            return direct_actions

        for xpath in (
            "xpath=ancestor::*[contains(translate(@class, "
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'search')][1]",
            "xpath=ancestor::payment-search-box[1]",
            "xpath=ancestor::*[self::div or self::form or self::oj-form-layout][1]",
            "xpath=ancestor::*[self::div or self::form or self::oj-form-layout][2]",
            "xpath=ancestor::*[self::div or self::form or self::oj-form-layout][3]",
        ):
            try:
                scopes.append(search_field.locator(xpath))
            except Exception:
                continue

        for scope in scopes:
            action = self._visible_first(
                [
                    scope.locator("span.icon-search"),
                    scope.locator(".icon-search"),
                    scope.get_by_role("button", name=search_pattern),
                    scope.get_by_role("link", name=search_pattern),
                    scope.locator("button[aria-label*='search' i]"),
                    scope.locator("a[aria-label*='search' i]"),
                    scope.locator("[role='button'][aria-label*='search' i]"),
                    scope.locator("button[title*='search' i]"),
                    scope.locator("a[title*='search' i]"),
                    scope.locator("button"),
                    scope.locator("a"),
                    scope.locator("[role='button']"),
                ]
            )

            if action:
                return action

        return None

    def _find_first_employee_delete_action(self, timeout: float = 10):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if self._has_no_records_message():
                return None

            for frame in self.page.frames:
                for rows in self._record_locators(frame):
                    try:
                        count = rows.count()
                    except Exception:
                        continue

                    for index in range(count):
                        row = rows.nth(index)

                        try:
                            if not row.is_visible(timeout=500):
                                continue
                        except Exception:
                            continue

                        delete_action = self._find_delete_action_in_row(row)

                        if delete_action:
                            return delete_action

                delete_action = self._find_visible_delete_action(frame)

                if delete_action:
                    return delete_action

            self.page.wait_for_timeout(500)

        return None

    def _find_delete_action_in_row(self, row):
        delete_pattern = re.compile(r"(delete|remove)", re.I)
        return self._visible_enabled_first(
            [
                row.locator("img[alt*='delete' i][src*='delete' i]"),
                row.locator("img[alt*='delete' i]"),
                row.locator("img[src*='delete_benef' i]"),
                row.locator("[data-bind*='Delete' i]"),
                row.locator("[aria-label*='delete' i]"),
                row.locator("[title*='delete' i]"),
                row.locator("[id*='delete' i]"),
                row.locator("[class*='delete' i]"),
                row.locator("[class*='trash' i]"),
                row.locator("[class*='bin' i]"),
                row.get_by_role("button", name=delete_pattern),
                row.get_by_role("link", name=delete_pattern),
                row.locator("button").filter(has_text=delete_pattern),
                row.locator("a").filter(has_text=delete_pattern),
                row.locator("[role='button']").filter(has_text=delete_pattern),
            ]
        )

    def _find_visible_delete_action(self, frame):
        delete_pattern = re.compile(r"(delete|remove)", re.I)
        return self._visible_enabled_first(
            [
                frame.locator("tbody tr img[alt*='delete' i][src*='delete' i]"),
                frame.locator("tbody tr img[alt*='delete' i]"),
                frame.locator("tbody tr img[src*='delete_benef' i]"),
                frame.locator("tbody tr [data-bind*='Delete' i]"),
                frame.get_by_role("button", name=delete_pattern),
                frame.get_by_role("link", name=delete_pattern),
                frame.locator("[aria-label*='delete' i]"),
                frame.locator("[title*='delete' i]"),
                frame.locator("[id*='delete' i]"),
                frame.locator("[class*='delete' i]"),
                frame.locator("[class*='trash' i]"),
                frame.locator("[class*='bin' i]"),
            ]
        )

    def _click_employee_delete_action(self, delete_action):
        try:
            delete_action.click(timeout=10000, force=True)
            return
        except Exception:
            pass

        try:
            delete_action.evaluate("element => element.click()")
        except Exception as exc:
            raise AssertionError(f"Could not click employee delete icon: {exc}") from None

    def _record_locators(self, frame):
        return [
            frame.locator("tbody tr"),
            frame.locator(".oj-table-body-row"),
            frame.locator("tr"),
            frame.locator("[role='row']"),
            frame.locator(".oj-listview-item"),
            frame.locator(".oj-listview-item-element"),
            frame.locator("oj-list-item-layout"),
            frame.locator("li"),
            frame.locator("[data-oj-context]"),
            frame.locator("div[class*='employee' i]"),
            frame.locator("div[class*='salary' i]"),
            frame.locator("div[class*='list' i]"),
            frame.locator("div[class*='card' i]"),
        ]

    def _employee_snapshot(self) -> str:
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
            "tr, [role='row'], .oj-listview-item, .oj-listview-item-element, "
            "oj-list-item-layout, li, [data-oj-context], "
            "div[class*='employee' i], div[class*='salary' i], "
            "div[class*='list' i], div[class*='card' i]"
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

        return "\n".join(rows) or "No employee-like record elements were found."

    def _save_debug_artifacts(self) -> Path:
        artifact_dir = (
            Path("artifacts")
            / f"delete_bene_salary_{time.strftime('%Y%m%d_%H%M%S')}"
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
