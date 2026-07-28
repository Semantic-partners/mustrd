"""Record a short screen tour of the run viewer, for a PR comment or the docs.

GitHub sanitises HTML in comments — no script, no style — so a self-contained
interactive page cannot be embedded in a review. Short of hosting it somewhere, a
recording is the way to show the thing working without asking anyone to download
and unzip a build artifact.

    python scripts/record_viewer_demo.py [--report path.html] [--out demo.mp4]

Needs Playwright with chromium (`playwright install chromium`); converts the WebM
Playwright produces to MP4 when ffmpeg is present, because GitHub's blob viewer
plays MP4 reliably and WebM inconsistently.

A headless browser records no cursor, and `locator.click()` teleports — so a
viewer sees things happen with no idea what was clicked. So: a cursor is injected
into the page (CURSOR_SCRIPT) and every interaction glides the real mouse to the
target and presses it, which that cursor follows.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

VIEWPORT = {"width": 1280, "height": 800}

# A visible pointer, since the recording has none of its own. Follows real mouse
# events, shrinks while pressed, and leaves a ripple where it clicked. Styled to
# read against either theme.
CURSOR_SCRIPT = """
(() => {
  const install = () => {
    if (document.getElementById('__demo_cursor')) return;
    const style = document.createElement('style');
    style.textContent = `
      #__demo_cursor {
        position: fixed; left: -50px; top: -50px; width: 20px; height: 20px;
        margin: -10px 0 0 -10px; border-radius: 50%; z-index: 2147483647;
        pointer-events: none; background: rgba(255,255,255,.92);
        box-shadow: 0 0 0 2px rgba(0,0,0,.6), 0 3px 10px rgba(0,0,0,.45);
        transition: transform .09s ease;
      }
      #__demo_cursor.down { transform: scale(.62); }
      .__demo_ripple {
        position: fixed; width: 20px; height: 20px; margin: -10px 0 0 -10px;
        border-radius: 50%; z-index: 2147483646; pointer-events: none;
        border: 2px solid rgba(110,231,183,.95);
        animation: __demo_pulse .55s ease-out forwards;
      }
      @keyframes __demo_pulse {
        from { transform: scale(.6); opacity: 1; }
        to   { transform: scale(3.2); opacity: 0; }
      }
    `;
    document.head.appendChild(style);
    const dot = document.createElement('div');
    dot.id = '__demo_cursor';
    document.body.appendChild(dot);

    let x = -50, y = -50;
    addEventListener('mousemove', e => {
      x = e.clientX; y = e.clientY;
      dot.style.left = x + 'px';
      dot.style.top = y + 'px';
    }, true);
    addEventListener('mousedown', () => {
      dot.classList.add('down');
      const ripple = document.createElement('div');
      ripple.className = '__demo_ripple';
      ripple.style.left = x + 'px';
      ripple.style.top = y + 'px';
      document.body.appendChild(ripple);
      setTimeout(() => ripple.remove(), 600);
    }, true);
    addEventListener('mouseup', () => dot.classList.remove('down'), true);
  };
  if (document.readyState === 'loading') {
    addEventListener('DOMContentLoaded', install);
  } else {
    install();
  }
})();
"""


def beat(page, ms=900):
    """A pause long enough to read what just happened."""
    page.wait_for_timeout(ms)


def glide(page, locator, steps=22):
    """Move the real mouse to the middle of `locator`, so the injected cursor
    travels there visibly instead of jumping."""
    locator.scroll_into_view_if_needed()
    page.wait_for_timeout(120)                     # let any scroll settle first
    box = locator.bounding_box()
    if box is None:
        return False
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2,
                    steps=steps)
    return True


def click(page, locator, settle=280):
    """Glide to a target, pause so the viewer can see what is about to be hit,
    then press it."""
    if not glide(page, locator):
        return False
    page.wait_for_timeout(settle)
    page.mouse.down()
    page.wait_for_timeout(90)
    page.mouse.up()
    return True


def type_into(page, locator, text, delay=110):
    click(page, locator)
    page.wait_for_timeout(200)
    page.keyboard.type(text, delay=delay)


def tab(page, name):
    return click(page, page.get_by_role("tab", name=name))


def tour(page):
    """The tour, ordered as the story of a run: what passed, what the specs say,
    what the ontology coverage is, and what the report carries."""
    page.wait_for_selector("nav.tabs button")
    page.mouse.move(640, 700, steps=1)             # park the cursor on screen
    beat(page, 1500)                               # the tiles: pass rate, coverage

    # --- Tests: the tree, then one spec in full -----------------------------
    click(page, page.get_by_role("button", name="Expand all"))
    beat(page, 1300)

    # The spec's own Turtle, with the SPARQL inside must:queryText highlighted as
    # SPARQL rather than as one long string.
    query = page.locator("pre.code", has_text="SELECT").first
    query.scroll_into_view_if_needed()
    beat(page, 2000)

    # A must:file reference is a link to the dataset the page carries.
    click(page, page.locator("a.tok-file").first)
    beat(page, 2300)                               # the sheet: content, Download, Copy
    page.keyboard.press("Escape")
    beat(page)

    # --- Filtering: the caret stays where you put it ------------------------
    click(page, page.get_by_role("button", name="Collapse all"))
    beat(page, 500)
    field = page.get_by_placeholder("Filter tests…")
    type_into(page, field, "mayor")
    beat(page, 1500)
    field.fill("")
    beat(page, 600)

    # --- Coverage -----------------------------------------------------------
    tab(page, "Coverage")
    beat(page, 1700)                               # the subClassOf tree
    row = page.locator("tr.term", has_text="place:City").first
    click(page, row)
    beat(page, 1800)                               # which tests exercise the term
    click(page, row)

    chip = page.locator(".chip", has_text="query-only").first
    if chip.count():
        click(page, chip)
        beat(page, 1700)                           # the gap: named but never populated
        click(page, chip)
        beat(page, 400)

    # --- Competency questions ----------------------------------------------
    if page.get_by_role("tab", name="Competency questions").count():
        tab(page, "Competency questions")
        beat(page, 2000)

    # --- Files --------------------------------------------------------------
    tab(page, "Files")
    beat(page, 1200)
    for name in ("mayor.ttl", "region-lookup.mustrd.ttl"):
        item = page.locator(".fileitem", has_text=name).first
        if item.count():
            click(page, item)
            beat(page, 1400)
    type_into(page, page.get_by_placeholder("Filter files…"), "Mayor")
    beat(page, 1700)                               # the filter searches file contents
    page.get_by_placeholder("Filter files…").fill("")
    beat(page, 400)

    # --- Issues: what the run noticed about the ontology --------------------
    if page.get_by_role("tab", name="Issues").count():
        tab(page, "Issues")
        beat(page, 2300)                           # used-but-not-declared, TBox in data

    # --- The graph it is all rendered from ----------------------------------
    tab(page, "Graph")
    beat(page, 2000)

    # --- and it reads in either theme --------------------------------------
    tab(page, "Coverage")
    beat(page, 600)
    click(page, page.get_by_title("Toggle light / dark"))
    beat(page, 2800)


def record(report: Path, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    raw_dir = out.parent / "_recording"
    if raw_dir.exists():
        shutil.rmtree(raw_dir)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport=VIEWPORT, record_video_dir=str(raw_dir),
            record_video_size=VIEWPORT, device_scale_factor=1,
            # Headless chromium reports prefers-color-scheme: light; dark is the
            # look most people get, and the highlighting reads better in it.
            color_scheme="dark",
        )
        context.add_init_script(CURSOR_SCRIPT)
        page = context.new_page()
        page.goto(report.resolve().as_uri())
        tour(page)
        video = page.video
        context.close()                            # flushes the file
        browser.close()
        webm = Path(video.path())

    if shutil.which("ffmpeg") is None:
        final = out.with_suffix(".webm")
        shutil.move(str(webm), final)
        print(f"ffmpeg not found; left the WebM at {final}")
    else:
        final = out
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(webm),
             "-movflags", "+faststart",             # starts playing before fully loaded
             "-pix_fmt", "yuv420p",                 # the profile browsers all decode
             "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
             "-crf", "30", str(final)],
            check=True)
    shutil.rmtree(raw_dir, ignore_errors=True)
    return final


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", default="docs/examples/geography-example/report/index.html")
    ap.add_argument("--out", default="viewer-demo.mp4")
    args = ap.parse_args()

    report = Path(args.report)
    if not report.is_file():
        raise SystemExit(f"no report at {report} — build one with `mustrd report --viewer`")

    final = record(report, Path(args.out))
    size = final.stat().st_size
    print(f"{final} — {size / 1024:.0f} KB")
    if size > 10 * 1024 * 1024:
        print("warning: over 10MB, which is GitHub's attachment limit", file=sys.stderr)


if __name__ == "__main__":
    main()
