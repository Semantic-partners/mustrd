"""Record a short screen tour of the mustrd run viewer.

    python scripts/record_viewer_demo.py [--report path.html] [--out demo.mp4]

GitHub sanitises HTML in comments — no script, no style — so a self-contained
interactive page cannot be embedded in a review, and there is no API for attaching
media to a comment either. A recording is what is left.

The recording machinery is in demo_recorder.py, which knows nothing about mustrd;
only `tour` below does. Needs `playwright install chromium`.
"""
import argparse
from pathlib import Path

from demo_recorder import record

DEFAULT_REPORT = "docs/examples/geography-example/report/index.html"


def tour(d):
    """Ordered as the story of a run: what passed, what the specs say, how much of
    the ontology they reach, and what the report carries."""
    d.beat(1500)                                       # the tiles: pass rate, coverage

    # --- Tests: the tree, then one spec in full -----------------------------
    d.click(d.button("Expand all"))
    d.beat(1300)

    # The spec's Turtle, with the SPARQL inside must:queryText highlighted as
    # SPARQL rather than as one long string.
    d.page.locator("pre.code", has_text="SELECT").first.scroll_into_view_if_needed()
    d.beat(2000)

    # A must:file reference is a link to the dataset the page carries.
    d.click(d.page.locator("a.tok-file").first)
    d.beat(2300)                                       # the sheet: content, Download, Copy
    d.press("Escape")
    d.beat()

    # --- Filtering: the caret stays where you put it ------------------------
    d.click(d.button("Collapse all"))
    d.beat(500)
    d.type_into(d.find("Filter tests…"), "mayor")
    d.beat(1500)
    d.find("Filter tests…").fill("")
    d.beat(600)

    # --- Coverage -----------------------------------------------------------
    d.click(d.tab("Coverage"))
    d.beat(1700)                                       # the subClassOf tree
    row = d.page.locator("tr.term", has_text="place:City").first
    d.click(row)
    d.beat(1800)                                       # which tests exercise the term
    d.click(row)

    chip = d.page.locator(".chip", has_text="query-only").first
    if chip.count():
        d.click(chip)
        d.beat(1700)                                   # named by a query, never populated
        d.click(chip)
        d.beat(400)

    # --- Competency questions ----------------------------------------------
    if d.tab("Competency questions").count():
        d.click(d.tab("Competency questions"))
        d.beat(2000)

    # --- Files --------------------------------------------------------------
    d.click(d.tab("Files"))
    d.beat(1200)
    for name in ("mayor.ttl", "region-lookup.mustrd.ttl"):
        item = d.page.locator(".fileitem", has_text=name).first
        if item.count():
            d.click(item)
            d.beat(1400)
    d.type_into(d.find("Filter files…"), "Mayor")
    d.beat(1700)                                       # the filter searches file contents
    d.find("Filter files…").fill("")
    d.beat(400)

    # --- Issues: what the run noticed about the ontology --------------------
    if d.tab("Issues").count():
        d.click(d.tab("Issues"))
        d.beat(2300)                                   # used-but-not-declared, TBox in data

    # --- The graph it is all rendered from ----------------------------------
    d.click(d.tab("Graph"))
    d.beat(2000)

    # --- and it reads in either theme --------------------------------------
    d.click(d.tab("Coverage"))
    d.beat(600)
    d.click(d.page.get_by_title("Toggle light / dark"))
    d.beat(2800)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", default=DEFAULT_REPORT)
    ap.add_argument("--out", default="viewer-demo.mp4")
    args = ap.parse_args()

    if not Path(args.report).is_file():
        raise SystemExit(
            f"no report at {args.report} — build one with `mustrd report --viewer`")

    final = record(args.report, tour, out=args.out, ready="nav.tabs button")
    print(f"{final} — {final.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
