import re
import time
from pathlib import Path

from playwright.sync_api import Page


class MsmeLoginPage:
    def __init__(self, page: Page, login_url: str):
        self.page = page
        self.login_url = login_url
        self.console_messages = []
        self.request_failures = []
        self._capture_debug_events()

    def login(self, username: str, password: str, otp: str):
        try:
            username_field, password_field = self._open_login_page()
            self._type_like_user(username_field, username)
            self._type_like_user(password_field, password, verify_value=False)

            self._click_action(
                re.compile(r"^\s*login\s*$", re.I),
                "login button",
                value_fragments=("Login",),
            )

            otp_required = True

            try:
                self._fill_otp(otp)
            except AssertionError:
                if self._dashboard_loaded() or self._wait_for_dashboard_loaded(timeout=5):
                    otp_required = False
                elif self._login_form_visible():
                    self._click_action(
                        re.compile(r"^\s*login\s*$", re.I),
                        "login button",
                        value_fragments=("Login",),
                    )
                    self._fill_otp(otp)
                else:
                    raise

            if self._dashboard_loaded() or (
                not self._otp_challenge_visible()
                and self._wait_for_dashboard_loaded(timeout=5)
            ):
                otp_required = False

            if otp_required:
                self._click_login_confirm_and_proceed_if_required(timeout=30)

            self._wait_for_login_complete(otp)
        except AssertionError as exc:
            artifact_dir = self._save_debug_artifacts()
            raise AssertionError(
                f"{exc}\n\nDebug artifacts saved to: {artifact_dir.resolve()}"
            ) from None

    def _capture_debug_events(self):
        self.page.on(
            "console",
            lambda msg: self.console_messages.append(f"{msg.type}: {msg.text}"),
        )
        self.page.on(
            "pageerror",
            lambda exc: self.console_messages.append(f"pageerror: {exc}"),
        )
        self.page.on(
            "requestfailed",
            lambda request: self.request_failures.append(
                f"{request.method} {request.url} -> {request.failure}"
            ),
        )

    @staticmethod
    def _visible_first(locators):
        for locator in locators:
            try:
                for index in range(locator.count()):
                    candidate = locator.nth(index)
                    if candidate.is_visible():
                        return candidate
            except Exception:
                continue
        return None

    @staticmethod
    def _visible_enabled_first(locators):
        for locator in locators:
            try:
                for index in range(locator.count()):
                    candidate = locator.nth(index)
                    if candidate.is_visible() and candidate.is_enabled():
                        return candidate
            except Exception:
                continue
        return None

    def _input_snapshot(self) -> str:
        rows = []
        script = """
        els => els.map((e, idx) => ({
          idx,
          tag: e.tagName.toLowerCase(),
          type: e.getAttribute("type") || "",
          id: e.id || "",
          name: e.getAttribute("name") || "",
          placeholder: e.getAttribute("placeholder") || "",
          aria: e.getAttribute("aria-label") || "",
          visible: !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length)
        }))
        """

        for frame_index, frame in enumerate(self.page.frames):
            try:
                fields = frame.locator("input, textarea").evaluate_all(script)
            except Exception as exc:
                rows.append(f"frame={frame_index} url={frame.url} unavailable: {exc}")
                continue

            for field in fields:
                rows.append(
                    "frame={frame} url={url} idx={idx} tag={tag} type={type} "
                    "id={id} name={name} placeholder={placeholder} aria={aria} "
                    "visible={visible}".format(
                        frame=frame_index,
                        url=frame.url,
                        **field,
                    )
                )

        return "\n".join(rows) or "No input or textarea elements were found."

    def _action_snapshot(self) -> str:
        rows = []
        script = """
        els => els.map((e, idx) => ({
          idx,
          tag: e.tagName.toLowerCase(),
          type: e.getAttribute("type") || "",
          id: e.id || "",
          role: e.getAttribute("role") || "",
          value: e.getAttribute("value") || "",
          aria: e.getAttribute("aria-label") || "",
          title: e.getAttribute("title") || "",
          text: (e.innerText || e.textContent || "").trim().replace(/\\s+/g, " "),
          visible: !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length),
          disabled: !!e.disabled || e.getAttribute("aria-disabled") === "true"
        }))
        """
        selector = (
            "button, input[type='button'], input[type='submit'], a, "
            "[role='button'], oj-button"
        )

        for frame_index, frame in enumerate(self.page.frames):
            try:
                actions = frame.locator(selector).evaluate_all(script)
            except Exception as exc:
                rows.append(f"frame={frame_index} url={frame.url} unavailable: {exc}")
                continue

            for action in actions:
                rows.append(
                    "frame={frame} url={url} idx={idx} tag={tag} type={type} "
                    "id={id} role={role} value={value} aria={aria} title={title} "
                    "visible={visible} disabled={disabled} text={text}".format(
                        frame=frame_index,
                        url=frame.url,
                        **action,
                    )
                )

        return "\n".join(rows) or "No action elements were found."

    def _page_snapshot(self) -> str:
        rows = [
            f"url={self.page.url}",
            f"title={self.page.title()}",
            f"frames={len(self.page.frames)}",
        ]

        for frame_index, frame in enumerate(self.page.frames):
            try:
                ready_state = frame.evaluate("document.readyState")
                body_text = frame.locator("body").inner_text(timeout=1000)[:1000]
            except Exception as exc:
                ready_state = f"unavailable: {exc}"
                body_text = ""

            rows.append(
                f"frame={frame_index} url={frame.url} readyState={ready_state} "
                f"bodyText={body_text!r}"
            )

        return "\n".join(rows)

    def _save_debug_artifacts(self) -> Path:
        artifact_dir = Path("artifacts") / f"msme_login_{time.strftime('%Y%m%d_%H%M%S')}"
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

    def _find_login_fields(self, timeout: float = 30):
        username_text = re.compile(
            r"(user\s*name|user\s*id|login\s*id|customer\s*id)",
            re.I,
        )
        password_text = re.compile(r"password", re.I)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                username = self._visible_first(
                    [
                        frame.get_by_label(username_text),
                        frame.get_by_placeholder(username_text),
                        frame.get_by_role("textbox", name=username_text),
                        frame.locator('input[name*="user" i]'),
                        frame.locator('input[id*="user" i]'),
                        frame.locator('input[placeholder*="user" i]'),
                        frame.locator('input[name*="login" i]'),
                        frame.locator('input[id*="login" i]'),
                        frame.locator('input[type="text"]'),
                        frame.locator("input:not([type])"),
                    ]
                )
                password = self._visible_first(
                    [
                        frame.get_by_label(password_text),
                        frame.get_by_placeholder(password_text),
                        frame.locator('input[type="password"]'),
                        frame.locator('input[name*="pass" i]'),
                        frame.locator('input[id*="pass" i]'),
                        frame.locator('input[placeholder*="pass" i]'),
                    ]
                )

                if username and password:
                    return username, password

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Could not find login fields.\n"
            f"{self._page_snapshot()}\n\n"
            f"{self._input_snapshot()}"
        )

    def _type_like_user(self, locator, value: str, verify_value: bool = True):
        locator.click(timeout=10000)
        locator.press("Control+A")
        locator.press("Backspace")

        try:
            locator.press_sequentially(value, delay=75)
        except AttributeError:
            locator.type(value, delay=75)

        try:
            actual_value = locator.input_value(timeout=1000)
        except Exception:
            actual_value = value

        is_masked_value = bool(actual_value) and set(actual_value) <= {"*"}

        if verify_value and actual_value != value and not is_masked_value:
            raise AssertionError(
                f"Expected field value to be {value!r}, but browser has {actual_value!r}."
            )

        locator.press("Tab")

    def _open_login_page(self):
        attempts = [
            self.login_url,
            f"{self.login_url}&_={int(time.time())}",
            self.login_url,
        ]
        last_error = None

        for attempt, url in enumerate(attempts, start=1):
            try:
                self.page.context.clear_cookies()
                self.page.goto("about:blank")
                self.page.goto(url, wait_until="load", timeout=60000)

                try:
                    self.page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass

                return self._find_login_fields(timeout=15)
            except AssertionError as exc:
                last_error = exc

                if "login-form-main" not in self.page.url and attempt < len(attempts):
                    try:
                        self.page.goto(
                            self.login_url,
                            wait_until="domcontentloaded",
                            timeout=60000,
                        )
                    except Exception:
                        pass

                if attempt < len(attempts):
                    try:
                        self.page.reload(wait_until="load", timeout=60000)
                    except Exception:
                        pass

        raise AssertionError(
            "Could not open the login page after multiple attempts.\n"
            f"Last error:\n{last_error}"
        )

    @staticmethod
    def _input_value_locators(frame, fragments):
        locators = []

        for fragment in fragments:
            locators.append(
                frame.locator(
                    f"input[type='button'][value*='{fragment}' i], "
                    f"input[type='submit'][value*='{fragment}' i]"
                )
            )

        return locators

    def _find_action(
        self,
        label_pattern,
        description: str,
        value_fragments=(),
        timeout: float = 30,
    ):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                action = self._visible_enabled_first(
                    [
                        frame.get_by_role("button", name=label_pattern),
                        frame.get_by_role("link", name=label_pattern),
                        frame.locator("button").filter(has_text=label_pattern),
                        frame.locator("oj-button").filter(has_text=label_pattern),
                        frame.locator("[role='button']").filter(has_text=label_pattern),
                        frame.locator("a").filter(has_text=label_pattern),
                        *self._input_value_locators(frame, value_fragments),
                    ]
                )

                if action:
                    return action

            self.page.wait_for_timeout(500)

        raise AssertionError(
            f"Could not find {description}.\n"
            f"{self._page_snapshot()}\n\n"
            f"{self._action_snapshot()}"
        )

    def _find_action_optional(
        self,
        label_pattern,
        value_fragments=(),
        timeout: float = 1,
    ):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            for frame in self.page.frames:
                action = self._visible_enabled_first(
                    [
                        frame.get_by_role("button", name=label_pattern),
                        frame.get_by_role("link", name=label_pattern),
                        frame.locator("button").filter(has_text=label_pattern),
                        frame.locator("oj-button").filter(has_text=label_pattern),
                        frame.locator("[role='button']").filter(has_text=label_pattern),
                        frame.locator("a").filter(has_text=label_pattern),
                        *self._input_value_locators(frame, value_fragments),
                    ]
                )

                if action:
                    return action

            self.page.wait_for_timeout(200)

        return None

    def _click_action(self, label_pattern, description: str, value_fragments=()):
        action = self._find_action(label_pattern, description, value_fragments)

        try:
            action.click(timeout=10000)
        except Exception as exc:
            raise AssertionError(
                f"Found {description}, but click failed: {exc}\n"
                f"{self._page_snapshot()}\n\n"
                f"{self._action_snapshot()}"
            ) from None

    @staticmethod
    def _looks_like_otp_field(attrs):
        text = " ".join(
            str(attrs.get(key) or "")
            for key in ("id", "name", "placeholder", "aria", "autocomplete")
        )

        return bool(
            re.search(r"(otp|one\s*time|verification|security\s*code)", text, re.I)
            or attrs.get("inputmode") in ("numeric", "decimal")
            or attrs.get("type") in ("tel", "number")
            or attrs.get("maxlength") in ("1", "4", "6")
        )

    def _login_error_text(self):
        error_patterns = [
            re.compile(
                r"Incorrect\s+User\s+Credentials.*?(?:locked\.|$)",
                re.I | re.S,
            ),
            re.compile(
                r"Invalid\s+(?:User\s+ID|Password|credentials).*?(?:\.|$)",
                re.I | re.S,
            ),
        ]

        for frame in self.page.frames:
            try:
                text = frame.locator("body").inner_text(timeout=1000)
            except Exception:
                continue

            for pattern in error_patterns:
                match = pattern.search(text)

                if match:
                    return " ".join(match.group(0).split())

        return None

    def _body_text(self):
        body_parts = []

        for frame in self.page.frames:
            try:
                body_parts.append(frame.locator("body").inner_text(timeout=1000))
            except Exception:
                continue

        return "\n".join(body_parts)

    def _dashboard_loaded(self):
        body_text = self._body_text()
        url = self.page.url

        return bool(
            "login-form-main" not in url
            and (
                (
                    re.search(r"\bPayments\b", body_text, re.I)
                    and re.search(r"\bHome\b", body_text, re.I)
                )
                or (
                    re.search(r"\bLast\s+login\b", body_text, re.I)
                    and re.search(r"\bLogout\b", body_text, re.I)
                )
                or (
                    re.search(r"\bAccounts\b", body_text, re.I)
                    and re.search(r"\bRecent\s+Transactions\b", body_text, re.I)
                )
            )
        )

    def _wait_for_dashboard_loaded(self, timeout: float = 5):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if self._dashboard_loaded():
                return True

            self.page.wait_for_timeout(500)

        return self._dashboard_loaded()

    def _otp_challenge_visible(self):
        body_text = self._body_text()

        return bool(
            re.search(r"\bVerification\b", body_text, re.I)
            and re.search(r"\bEnter\s+OTP\b", body_text, re.I)
        )

    def _login_form_visible(self):
        body_text = self._body_text()

        return bool(
            "login-form-main" in self.page.url
            and re.search(r"\bUser\s+ID\b", body_text, re.I)
            and re.search(r"\bPassword\b", body_text, re.I)
            and re.search(r"\bLogin\b", body_text, re.I)
        )

    def _wait_for_login_complete(self, otp: str, timeout: float = 60):
        deadline = time.monotonic() + timeout
        retried_otp_submit = False

        while time.monotonic() < deadline:
            if self._dashboard_loaded():
                try:
                    self.page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass

                self.page.wait_for_timeout(1000)
                return

            login_error = self._login_error_text()

            if login_error:
                raise AssertionError(f"Login failed after OTP: {login_error}")

            if self._otp_challenge_visible() and not retried_otp_submit:
                self.page.wait_for_timeout(3000)

                if self._dashboard_loaded():
                    return

                self._fill_otp(otp)
                self._click_login_confirm_and_proceed_if_required(timeout=30)
                retried_otp_submit = True

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Login did not reach dashboard after OTP confirmation.\n"
            f"{self._page_snapshot()}\n\n"
            f"{self._action_snapshot()}"
        )

    def _click_login_confirm_and_proceed_if_required(self, timeout: float = 30):
        confirm_pattern = re.compile(r"^\s*confirm\s*and\s*proceed\s*$", re.I)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if self._dashboard_loaded():
                return False

            login_error = self._login_error_text()

            if login_error:
                raise AssertionError(f"Login failed before OTP confirmation: {login_error}")

            action = self._find_action_optional(
                confirm_pattern,
                value_fragments=("Confirm", "Proceed"),
                timeout=1,
            )

            if action:
                try:
                    action.click(timeout=10000)
                    return True
                except Exception as exc:
                    if (
                        self._dashboard_loaded()
                        or self._wait_for_dashboard_loaded(timeout=5)
                    ):
                        return False

                    raise AssertionError(
                        "Found Confirm and Proceed button, but click failed: "
                        f"{exc}\n{self._page_snapshot()}\n\n{self._action_snapshot()}"
                    ) from None

            if self._dashboard_loaded():
                return False

            self.page.wait_for_timeout(500)

        if self._dashboard_loaded() or self._wait_for_dashboard_loaded(timeout=10):
            return False

        raise AssertionError(
            "Could not find Confirm and Proceed button.\n"
            f"{self._page_snapshot()}\n\n"
            f"{self._action_snapshot()}"
        )

    def _find_otp_fields(self, otp_length: int, timeout: float = 30):
        otp_text = re.compile(r"(otp|one\s*time|verification|security\s*code)", re.I)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if self._dashboard_loaded():
                return []

            login_error = self._login_error_text()

            if login_error:
                raise AssertionError(f"Login failed before OTP: {login_error}")

            for frame in self.page.frames:
                single_otp = self._visible_enabled_first(
                    [
                        frame.locator('input[name*="otp" i]'),
                        frame.locator('input[id*="otp" i]'),
                        frame.locator('input[placeholder*="otp" i]'),
                        frame.locator('textarea[name*="otp" i]'),
                        frame.locator('textarea[id*="otp" i]'),
                        frame.locator('textarea[placeholder*="otp" i]'),
                        frame.locator('input[name*="verification" i]'),
                        frame.locator('input[id*="verification" i]'),
                        frame.get_by_placeholder(otp_text),
                        frame.get_by_role("textbox", name=otp_text),
                        frame.locator('input[inputmode="numeric"]'),
                        frame.locator('input[type="tel"]'),
                        frame.locator('input[type="number"]'),
                        frame.locator('input[maxlength="6"]'),
                    ]
                )

                if single_otp:
                    return [single_otp]

                otp_fields = []
                fields = frame.locator("input, textarea")

                try:
                    count = fields.count()
                except Exception:
                    continue

                for index in range(count):
                    field = fields.nth(index)

                    try:
                        if not field.is_visible() or not field.is_enabled():
                            continue

                        attrs = field.evaluate(
                            """
                            e => ({
                              type: (e.getAttribute("type") || "").toLowerCase(),
                              id: e.id || "",
                              name: e.getAttribute("name") || "",
                              placeholder: e.getAttribute("placeholder") || "",
                              aria: e.getAttribute("aria-label") || "",
                              autocomplete: e.getAttribute("autocomplete") || "",
                              inputmode: (e.getAttribute("inputmode") || "").toLowerCase(),
                              maxlength: e.getAttribute("maxlength") || ""
                            })
                            """
                        )
                    except Exception:
                        continue

                    if self._looks_like_otp_field(attrs):
                        otp_fields.append(field)

                if len(otp_fields) == 1:
                    return otp_fields

                if len(otp_fields) >= otp_length:
                    return otp_fields[:otp_length]

            self.page.wait_for_timeout(500)

        raise AssertionError(
            "Could not find OTP field.\n"
            f"{self._page_snapshot()}\n\n"
            f"{self._input_snapshot()}"
        )

    def _fill_otp(self, otp: str):
        otp_fields = self._find_otp_fields(len(otp))

        if not otp_fields:
            return

        try:
            if len(otp_fields) == 1:
                self._type_like_user(otp_fields[0], otp, verify_value=False)
                return

            for digit, field in zip(otp, otp_fields):
                self._type_like_user(field, digit, verify_value=False)
        except Exception as exc:
            raise AssertionError(
                f"Found OTP field, but fill failed: {exc}\n"
                f"{self._page_snapshot()}\n\n"
                f"{self._input_snapshot()}"
            ) from None
