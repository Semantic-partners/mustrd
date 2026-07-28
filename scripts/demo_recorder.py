"""Record a screen tour of a web page, with a visible cursor. Copy me anywhere.

No project coupling — one file, Playwright and (optionally) ffmpeg. Write a tour
and hand it over:

    from demo_recorder import record

    def tour(d):
        d.beat(1500)                                   # let the page land
        d.click(d.tab("Coverage"))
        d.type_into(d.find("Filter terms…"), "City")
        d.beat(2000)

    record("dist/index.html", tour, out="demo.mp4")

Three things a naive Playwright recording gets wrong, all handled here:

  - **No cursor.** A headless browser captures no pointer, and `locator.click()`
    teleports — so a viewer sees things change with no idea what caused it. A
    cursor is injected into the page and every interaction glides the real mouse
    to its target, which that cursor follows.
  - **The wrong theme.** Headless chromium reports `prefers-color-scheme: light`,
    so a page with a dark default records light unless the context asks.
  - **A file that will not play.** GitHub's blob viewer and most browsers want
    MP4, `yuv420p`, and `+faststart` to begin playing before the whole file has
    loaded. WebM out of Playwright satisfies none of that.

Needs `playwright install chromium`. Without ffmpeg it leaves the WebM in place.
"""
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

# A pointer for a recording that has none of its own. Follows real mouse events,
# shrinks while pressed, and leaves a ripple where it clicked. Deliberately styled
# to read against either a light or a dark page.
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

# Narrative overlay. Captions are drawn into the page — same trick as the cursor
# — so they are captured in the recording itself. No sidecar subtitle file (which
# GitHub's PR player ignores anyway) and no ffmpeg burn-in pass. A caption can sit
# in the lower third, or be anchored to a point so it reads next to whatever is
# being pointed at. Reads on a light or a dark page.
CAPTION_SCRIPT = """
(() => {
  const ensure = () => {
    let el = document.getElementById('__demo_caption');
    if (el) return el;
    const style = document.createElement('style');
    style.textContent = `
      #__demo_caption {
        position: fixed; z-index: 2147483646; pointer-events: none;
        max-width: 30rem; padding: 10px 16px; border-radius: 10px;
        background: rgba(17,20,24,.92); color: #fff;
        font: 500 15px/1.4 -apple-system, system-ui, sans-serif;
        box-shadow: 0 6px 24px rgba(0,0,0,.35);
        opacity: 0; transition: opacity .28s ease;
        left: 50%; bottom: 40px; transform: translateX(-50%);
      }
      #__demo_caption.point { transform: translate(-50%, -100%); }
    `;
    document.head.appendChild(style);
    el = document.createElement('div');
    el.id = '__demo_caption';
    document.body.appendChild(el);
    return el;
  };
  window.__demoSay = (text, opts) => {
    const el = ensure();
    el.textContent = text;
    if (opts && opts.x != null) {
      el.classList.add('point');
      el.style.left = opts.x + 'px';
      el.style.top = opts.y + 'px';
      el.style.bottom = 'auto';
    } else {
      el.classList.remove('point');
      el.style.top = 'auto';
      el.style.left = '50%';
      el.style.bottom = (opts && opts.bottom != null ? opts.bottom : 40) + 'px';
    }
    el.style.opacity = '1';
  };
  window.__demoHide = () => {
    const el = document.getElementById('__demo_caption');
    if (el) el.style.opacity = '0';
  };
})();
"""


class Demo:
    """The page, plus interactions the injected cursor can be seen doing.

    Everything goes through real mouse movement rather than `locator.click()`, so
    the recording shows what is being clicked and the page is driven the way a
    person drives it.
    """

    def __init__(self, page):
        self.page = page

    # --- timing ---------------------------------------------------------------
    def beat(self, ms=900):
        """Pause long enough for a viewer to read what just happened."""
        self.page.wait_for_timeout(ms)

    # --- narrative -----------------------------------------------------------
    def say(self, text, ms=2200, at=None, bottom=40):
        """Show a caption for `ms`, then hide it. By default it sits in the lower
        third; pass `at=<locator>` to anchor it just above that element, so the
        narrative reads next to whatever is on screen. Doubles as a beat."""
        opts = {"bottom": bottom}
        if at is not None:
            box = at.bounding_box()
            if box is not None:
                opts = {"x": box["x"] + box["width"] / 2, "y": max(box["y"] - 12, 40)}
        self.page.evaluate("([t, o]) => window.__demoSay(t, o)", [text, opts])
        self.page.wait_for_timeout(ms)
        self.page.evaluate("() => window.__demoHide()")
        self.page.wait_for_timeout(260)            # let it fade before the next move

    # --- finding things ------------------------------------------------------
    def find(self, placeholder):
        return self.page.get_by_placeholder(placeholder)

    def tab(self, name):
        return self.page.get_by_role("tab", name=name)

    def button(self, name):
        return self.page.get_by_role("button", name=name)

    def link(self, name):
        return self.page.get_by_role("link", name=name)

    def text(self, value, exact=True):
        return self.page.get_by_text(value, exact=exact)

    # --- interacting ---------------------------------------------------------
    def glide(self, locator, steps=22):
        """Move the real mouse to the middle of `locator`, so the cursor travels
        there visibly instead of jumping. False if it has no box to aim at."""
        locator.scroll_into_view_if_needed()
        self.page.wait_for_timeout(120)            # let any scroll settle first
        box = locator.bounding_box()
        if box is None:
            return False
        self.page.mouse.move(box["x"] + box["width"] / 2,
                             box["y"] + box["height"] / 2, steps=steps)
        return True

    def click(self, locator, settle=280, optional=False):
        """Glide to a target, pause so the viewer sees what is about to be hit,
        then press it. Raises if the target isn't there — a renamed control
        should fail the recording loudly, not silently drop the beat. Pass
        `optional=True` for a step that is allowed to be absent."""
        if not self.glide(locator):
            if optional:
                return False
            raise LookupError(f"click target not found or not visible: {locator}")
        self.page.wait_for_timeout(settle)
        self.page.mouse.down()
        self.page.wait_for_timeout(90)
        self.page.mouse.up()
        return True

    def select(self, locator, value=None, label=None):
        """Glide to a <select> so the cursor is seen on it, then choose an option
        (by value or visible label)."""
        self.glide(locator)
        self.page.wait_for_timeout(200)
        locator.select_option(value=value, label=label)

    def type_into(self, locator, text, delay=110):
        """Click into a field and type at a readable speed."""
        self.click(locator)
        self.page.wait_for_timeout(200)
        self.page.keyboard.type(text, delay=delay)

    def press(self, key):
        self.page.keyboard.press(key)

    def park(self, x=None, y=None):
        """Put the cursor somewhere on screen, so it does not start in a corner."""
        width, height = self.page.viewport_size.values()
        self.page.mouse.move(x if x is not None else width / 2,
                             y if y is not None else height * 0.85, steps=1)


def _to_url(target):
    target = str(target)
    if "://" in target:
        return target
    return Path(target).resolve().as_uri()


def _to_mp4(webm: Path, out: Path, crf: int) -> Path:
    if shutil.which("ffmpeg") is None:
        final = out.with_suffix(".webm")
        shutil.move(str(webm), final)
        print(f"ffmpeg not found; left the WebM at {final}", file=sys.stderr)
        return final
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(webm),
         "-movflags", "+faststart",              # play before fully downloaded
         "-pix_fmt", "yuv420p",                  # the profile browsers all decode
         "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",   # h264 needs even dimensions
         "-crf", str(crf), str(out)],
        check=True)
    return out


def record(target, tour, out="demo.mp4", viewport=(1280, 800),
           color_scheme="dark", crf=30, ready=None):
    """Record `tour` against `target`, returning the path written.

    `target` is a URL or a local path. `tour` takes a `Demo`. `ready` is an
    optional selector to wait for before the tour starts.
    """
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    raw_dir = out.parent / "_recording"
    if raw_dir.exists():
        shutil.rmtree(raw_dir)

    size = {"width": viewport[0], "height": viewport[1]}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport=size, record_video_dir=str(raw_dir), record_video_size=size,
            device_scale_factor=1, color_scheme=color_scheme,
        )
        context.add_init_script(CURSOR_SCRIPT)
        context.add_init_script(CAPTION_SCRIPT)
        page = context.new_page()
        page.goto(_to_url(target))
        if ready:
            page.wait_for_selector(ready)
        demo = Demo(page)
        demo.park()
        tour(demo)
        video = page.video
        context.close()                          # flushes the file
        browser.close()
        webm = Path(video.path())

    final = _to_mp4(webm, out, crf)
    shutil.rmtree(raw_dir, ignore_errors=True)
    if final.stat().st_size > 10 * 1024 * 1024:
        print("warning: over 10MB, GitHub's attachment limit", file=sys.stderr)
    return final
