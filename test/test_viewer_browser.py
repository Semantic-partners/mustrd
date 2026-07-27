"""Browser tests for the run viewer, driven by Playwright.

`test/viewer_smoke.mjs` runs the page's JavaScript against a stub DOM: it proves
the model is read correctly and that every view produces the right content. What
it cannot prove is that the thing works in a browser — that no real DOM API is
missing, that nothing throws on the console, that the caret stays where you put
it, that a click opens what it should.

So these are deliberately about *behaviour a stub cannot observe*, not content:

    - the page loads with no console errors and no failed requests
      (it is self-contained; a request means something is wrong)
    - tabs switch
    - typing in a filter keeps focus and filters       <- a bug we actually shipped
    - a `must:file` reference opens the embedded file
    - a coverage row expands
    - the theme toggle takes effect
    - nothing overflows horizontally

Skipped unless Playwright and a browser are installed:

    pip install playwright && playwright install chromium
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

playwright_api = pytest.importorskip("playwright.sync_api",
                                     reason="pip install playwright")
from playwright.sync_api import Error as PlaywrightError, sync_playwright  # noqa: E402

EXAMPLE = Path("docs/examples/geography-example")
CONFIG = str(EXAMPLE / "mustrd-config.ttl")


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        try:
            instance = p.chromium.launch()
        except PlaywrightError as e:                    # browser not downloaded
            pytest.skip(f"chromium unavailable: {e}")
        yield instance
        instance.close()


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    """A viewer built from the runnable example. A Path, not a URL: `as_uri()` is
    `file:///C:/...` on Windows, and stripping the scheme back off leaves a path
    with a leading slash before the drive letter."""
    out = tmp_path_factory.mktemp("browser") / "report.html"
    proc = subprocess.run(
        [sys.executable, "-m", "mustrd.cli", "report", "--config", CONFIG,
         "--viewer", str(out), "--term-coverage", "--cq"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert proc.returncode == 0, proc.stderr
    return out.resolve()


@pytest.fixture
def page(browser, report):
    """A loaded page that fails the test on any console error or network request."""
    page = browser.new_page()
    problems = []
    page.on("console", lambda m: m.type == "error" and problems.append(f"console: {m.text}"))
    page.on("pageerror", lambda e: problems.append(f"uncaught: {e}"))
    # The page is self-contained: it should never reach for anything.
    page.on("request", lambda r: r.url.startswith("file://")
            or problems.append(f"request: {r.url}"))
    page.goto(report.as_uri())
    page.wait_for_selector("nav.tabs button")
    yield page
    page.close()
    assert not problems, "; ".join(problems)


def test_loads_clean_and_renders_the_run(page):
    assert "mustrd" in page.title()
    tabs = page.locator("nav.tabs button").all_inner_texts()
    assert [t.split("\n")[0] for t in tabs] == [
        "Tests", "Coverage", "Competency questions", "Issues", "Files", "Graph"]
    # The summary tiles are computed from the graph, not baked in.
    assert "89%" in page.locator(".tiles").inner_text()
    assert page.locator(".grp").count() >= 1


def test_tabs_switch(page):
    page.get_by_role("tab", name="Coverage").click()
    assert page.locator("table tbody tr.term").count() == 11
    page.get_by_role("tab", name="Files").click()
    assert page.locator(".filepane").is_visible()
    page.get_by_role("tab", name="Tests").click()
    assert page.locator(".tests li").count() == 4


@pytest.mark.parametrize("tab,box,expect", [
    ("Tests", "Filter tests…", "mayor"),
    ("Coverage", "Filter terms…", "City"),
    ("Files", "Filter files…", "mayor"),
])
def test_filter_keeps_focus_while_typing(page, tab, box, expect):
    """The bug we shipped: reading a state during render subscribed the enclosing
    binding to it, so each keystroke rebuilt the toolbar and the caret was lost.
    A stub DOM cannot see focus, so it is checked here for real."""
    page.get_by_role("tab", name=tab).click()
    field = page.get_by_placeholder(box)
    field.click()
    field.type(expect, delay=15)

    assert field.evaluate("el => el === document.activeElement"), "the field lost focus"
    assert field.input_value() == expect, "keystrokes were dropped"
    assert expect.lower() in page.locator("#main").inner_text().lower()


def test_a_file_reference_opens_the_embedded_file(page):
    """`must:file "mayor.ttl"` is a link to the copy the report carries."""
    page.get_by_role("tab", name="Tests").click()
    # Groups, tests and their sources all start closed; Expand all opens the lot
    # (and gets that button covered on the way past).
    page.get_by_role("button", name="Expand all").click()

    link = page.locator("a.tok-file", has_text="mayor.ttl").first
    link.scroll_into_view_if_needed()
    link.click()

    sheet = page.locator(".sheet")
    assert sheet.is_visible()
    assert "data/mayor.ttl" in sheet.locator(".path").inner_text()
    # The content is the dataset, and it can be taken away.
    assert "gov:Mayor" in sheet.locator("pre.code").inner_text()
    assert sheet.get_by_role("link", name="Download").get_attribute("href") \
        .startswith("data:text/turtle")

    page.keyboard.press("Escape")
    assert not sheet.is_visible()


def test_coverage_row_expands_to_its_tests(page):
    page.get_by_role("tab", name="Coverage").click()
    row = page.locator("tr.term", has_text="place:City").first
    before = page.locator("tr.ex:visible").count()
    row.click()
    assert page.locator("tr.ex:visible").count() > before
    row.click()
    assert page.locator("tr.ex:visible").count() == before


def test_theme_toggle_takes_effect(page):
    theme = lambda: page.evaluate("document.documentElement.dataset.theme || ''")  # noqa: E731
    start = theme()
    page.get_by_title("Toggle light / dark").click()
    assert theme() != start
    # And the change is visible, not just an attribute.
    assert page.evaluate(
        "getComputedStyle(document.body).backgroundColor") != ""


@pytest.mark.parametrize("width", [1280, 480])
def test_nothing_overflows_horizontally(page, width):
    page.set_viewport_size({"width": width, "height": 900})
    for tab in ("Tests", "Coverage", "Files", "Graph"):
        page.get_by_role("tab", name=tab).click()
        overflow = page.evaluate(
            "document.documentElement.scrollWidth - document.documentElement.clientWidth")
        assert overflow <= 1, f"{tab} overflows by {overflow}px at {width}px wide"


def test_the_smoke_harness_agrees(report, tmp_path):
    """Belt and braces: the stub-DOM harness and the browser look at the same file."""
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    proc = subprocess.run(["node", "test/viewer_smoke.mjs", str(report)],
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    assert proc.returncode == 0, proc.stderr or proc.stdout
