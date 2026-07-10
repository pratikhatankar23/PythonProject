import base64
import re
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

try:
    from pytest_html import extras as pytest_html_extras
except ImportError:
    pytest_html_extras = None


BASE_URL = "http://ofss-mum-1548.snbomprshared1.gbucdsint02bom.oraclevcn.com:6777/?page=login-form-main"
TIMEZONE_ID = "Asia/Kolkata"
LOCALE = "en-US"
REPORTS_DIR_NAME = "Reports"
SCREENSHOTS_DIR_NAME = "screenshots"
TEST_RESULTS_DIR_NAME = "test-results"
TRACE_FILE_NAME = "trace.zip"


def pytest_addoption(parser):
    parser.addoption(
        "--browser_name",
        action="store",
        default="chrome",
        help="Browser to run tests on: chrome, chromium, firefox, edge, msedge, safari, or webkit.",
    )


def pytest_configure(config):
    report_dir = _html_report_directory(config)
    screenshots_dir = report_dir / SCREENSHOTS_DIR_NAME

    report_dir.mkdir(parents=True, exist_ok=True)
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    config._msme_reports_dir = report_dir
    config._msme_screenshots_dir = screenshots_dir


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{call.when}", report)

    if call.when != "call" or report.outcome not in ("passed", "failed"):
        return

    page = item.funcargs.get("page")
    if not page:
        return

    screenshot_path, screenshot_bytes = _capture_test_screenshot(item, report, page)
    if screenshot_path and screenshot_bytes:
        _attach_screenshot_to_html_report(report, screenshot_bytes, screenshot_path)


def _html_report_directory(config):
    html_path = getattr(config.option, "htmlpath", None)

    if html_path:
        report_path = Path(html_path)
        if not report_path.is_absolute():
            report_path = Path.cwd() / report_path

        return report_path.parent

    return Path.cwd() / REPORTS_DIR_NAME


def _capture_test_screenshot(item, report, page):
    screenshots_dir = getattr(
        item.config,
        "_msme_screenshots_dir",
        Path.cwd() / REPORTS_DIR_NAME / SCREENSHOTS_DIR_NAME,
    )
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    screenshot_name = f"{_safe_file_name(item.nodeid)}_{report.outcome}.png"
    screenshot_path = screenshots_dir / screenshot_name

    try:
        screenshot_bytes = page.screenshot(path=str(screenshot_path), full_page=True)
    except Exception:
        return None, None

    if screenshot_bytes is None:
        try:
            screenshot_bytes = screenshot_path.read_bytes()
        except Exception:
            return None, None

    return screenshot_path, screenshot_bytes


def _attach_screenshot_to_html_report(report, screenshot_bytes, screenshot_path):
    if pytest_html_extras is None:
        return

    encoded_screenshot = base64.b64encode(screenshot_bytes).decode("utf-8")
    extra = getattr(report, "extras", [])
    extra.append(
        pytest_html_extras.png(
            encoded_screenshot,
            name=f"{report.outcome.title()} screenshot: {screenshot_path.name}",
        )
    )
    report.extras = extra


def _safe_file_name(value):
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")
    return safe_name[:180] or "test"


def _start_trace_if_requested(context, request):
    if _tracing_option(request.config) not in ("on", "retain-on-failure"):
        return False

    context.tracing.start(
        title=request.node.nodeid,
        screenshots=True,
        snapshots=True,
        sources=True,
    )
    return True


def _stop_trace_if_requested(context, request, trace_started):
    if not trace_started:
        return

    if _should_save_trace(request):
        trace_path = _trace_path(request)
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        if trace_path.exists():
            trace_path.unlink()
        context.tracing.stop(path=str(trace_path))
        return

    context.tracing.stop()


def _should_save_trace(request):
    tracing_option = _tracing_option(request.config)
    if tracing_option == "on":
        return True

    if tracing_option != "retain-on-failure":
        return False

    for phase in ("setup", "call"):
        report = getattr(request.node, f"rep_{phase}", None)
        if report and report.failed:
            return True

    return False


def _tracing_option(config):
    try:
        return config.getoption("--tracing")
    except (AttributeError, ValueError):
        return "off"


def _trace_path(request):
    return (
        _trace_output_dir(request.config)
        / _safe_file_name(request.node.nodeid)
        / TRACE_FILE_NAME
    )


def _trace_output_dir(config):
    try:
        output_path = config.getoption("--output")
    except (AttributeError, ValueError):
        output_path = TEST_RESULTS_DIR_NAME

    output_dir = Path(output_path or TEST_RESULTS_DIR_NAME)
    if not output_dir.is_absolute():
        output_dir = Path.cwd() / output_dir

    return output_dir


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def browser_name(request):
    return request.config.getoption("--browser_name").strip().lower()


@pytest.fixture(scope="session")
def playwright_instance():
    with sync_playwright() as playwright:
        yield playwright


@pytest.fixture(scope="function")
def browser(playwright_instance, browser_name):
    browser_instance = _launch_browser(playwright_instance, browser_name)
    yield browser_instance
    browser_instance.close()


@pytest.fixture(scope="function")
def context(browser, browser_name, request):
    context_instance = browser.new_context(
        no_viewport=True,
        locale=LOCALE,
        timezone_id=TIMEZONE_ID,
        ignore_https_errors=True,
        service_workers="block",
        user_agent=_user_agent(browser_name),
    )
    trace_started = _start_trace_if_requested(context_instance, request)

    try:
        yield context_instance
    finally:
        try:
            _stop_trace_if_requested(context_instance, request, trace_started)
        finally:
            context_instance.close()


@pytest.fixture(scope="function")
def page(context, base_url, request):
    page_instance = context.new_page()

    base_url_maximized = {"done": False}

    def maximize_when_base_url_opens(frame):
        try:
            if base_url_maximized["done"] or frame.parent_frame is not None:
                return

            if frame.url.startswith(base_url):
                base_url_maximized["done"] = True
                _maximize_browser_window(page_instance)
        except Exception:
            pass

    page_instance.on("framenavigated", maximize_when_base_url_opens)
    yield page_instance

    report = getattr(request.node, "rep_call", None)
    if report and report.outcome in ("passed", "failed"):
        try:
            page_instance.wait_for_timeout(5000)
        except Exception:
            pass


def _launch_browser(playwright, browser_name):
    chromium_args = [
        "--disable-blink-features=AutomationControlled",
        "--window-position=0,0",
        "--start-maximized",
    ]
    launch_options = {"headless": False}

    if browser_name in ("chrome", "google-chrome"):
        try:
            return playwright.chromium.launch(
                channel="chrome",
                args=chromium_args,
                **launch_options,
            )
        except Exception:
            return playwright.chromium.launch(args=chromium_args, **launch_options)

    if browser_name in ("edge", "msedge"):
        try:
            return playwright.chromium.launch(
                channel="msedge",
                args=chromium_args,
                **launch_options,
            )
        except Exception:
            return playwright.chromium.launch(args=chromium_args, **launch_options)

    if browser_name in ("chromium", "cr"):
        return playwright.chromium.launch(args=chromium_args, **launch_options)

    if browser_name in ("firefox", "ff"):
        return playwright.firefox.launch(**launch_options)

    if browser_name in ("safari", "webkit", "wk"):
        return playwright.webkit.launch(**launch_options)

    raise pytest.UsageError(
        "Unsupported browser_name. Use chrome, chromium, firefox, edge, msedge, safari, or webkit."
    )


def _maximize_browser_window(page):
    try:
        browser = page.context.browser
        if browser and browser.browser_type.name == "chromium":
            session = page.context.new_cdp_session(page)
            window = session.send("Browser.getWindowForTarget")
            session.send(
                "Browser.setWindowBounds",
                {
                    "windowId": window["windowId"],
                    "bounds": {"windowState": "maximized"},
                },
            )
    except Exception:
        pass

    try:
        page.evaluate("window.dispatchEvent(new Event('resize'))")
    except Exception:
        pass


def _user_agent(browser_name):
    if browser_name in ("firefox", "ff"):
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
            "Gecko/20100101 Firefox/125.0"
        )

    if browser_name in ("safari", "webkit", "wk"):
        return (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"
        )

    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
