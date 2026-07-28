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
    d.say("One self-contained HTML file. No server, no build step —"
          " it carries the run's RDF and renders itself.", 3000)
    d.say("Every number here is computed in the browser from that graph.", 2600)

    # --- Tests: the tree, then one spec in full -----------------------------
    d.click(d.button("Expand all"))
    d.beat(1200)
    d.say("Each test carries the spec that defines it.", 2200)

    # The spec's Turtle, with the SPARQL inside must:queryText highlighted as
    # SPARQL rather than as one long string.
    d.page.locator("pre.code", has_text="SELECT").first.scroll_into_view_if_needed()
    d.say("The SPARQL inside must:queryText is highlighted as SPARQL,"
          " not as one long string.", 3000)

    # A must:file reference is a link to the dataset the page carries.
    d.say("A must:file reference is a link — the report embeds the data too.", 2600)
    d.click(d.page.locator("a.tok-file").first)
    d.beat(1200)
    d.say("The dataset the test actually loaded. Download or copy it.", 2800)
    d.press("Escape")
    d.beat()

    # --- Filtering: the caret stays where you put it ------------------------
    d.click(d.button("Collapse all"))
    d.beat(500)
    d.type_into(d.find("Filter tests…"), "mayor")
    d.say("Filters as you type.", 1800)
    d.find("Filter tests…").fill("")
    d.beat(600)

    # --- Coverage -----------------------------------------------------------
    d.click(d.tab("Coverage"))
    d.say("How much of your ontology the tests actually exercise —"
          " nested by rdfs:subClassOf.", 3200)
    row = d.page.locator("tr.term", has_text="place:City").first
    d.click(row)
    d.say("Click a term for the tests behind it.", 2200)
    d.click(row)

    chip = d.page.locator(".chip", has_text="query-only").first
    if chip.count():
        d.click(chip)
        d.say("query-only: named by a query but never populated,"
              " so it does not count as covered.", 3000)
        d.click(chip)
        d.beat(400)

    # --- Competency questions ----------------------------------------------
    if d.tab("Competency questions").count():
        d.click(d.tab("Competency questions"))
        d.say("Competency questions, and which test answers each one.", 2800)

    # --- Files --------------------------------------------------------------
    d.click(d.tab("Files"))
    d.say("Every file the run read, embedded in the page.", 2400)
    for name in ("mayor.ttl", "region-lookup.mustrd.ttl"):
        item = d.page.locator(".fileitem", has_text=name).first
        if item.count():
            d.click(item)
            d.beat(1400)
    d.type_into(d.find("Filter files…"), "Mayor")
    d.say("The filter searches file contents, not just names.", 2600)
    d.find("Filter files…").fill("")
    d.beat(400)

    # --- Issues: what the run noticed about the ontology --------------------
    if d.tab("Issues").count():
        d.click(d.tab("Issues"))
        d.say("Terms a test uses that the ontology never declares.", 2800)

    # --- The graph it is all rendered from ----------------------------------
    d.click(d.tab("Graph"))
    d.say("And the RDF it was all rendered from — take it away and query it.", 3000)

    # --- and it reads in either theme --------------------------------------
    d.click(d.tab("Coverage"))
    d.beat(600)
    d.click(d.page.get_by_title("Toggle light / dark"))
    d.beat(2600)


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
