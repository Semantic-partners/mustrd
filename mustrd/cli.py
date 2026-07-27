"""The `mustrd` command-line tool.

Runs a MustrdTest configuration (the same TTL config the pytest plugin uses) and
produces the same reports — coverage / competency questions / Markdown / RDF —
WITHOUT pytest. Spec execution goes through mustrd.runner and reporting goes
through mustrd.reporting, the shared libraries the pytest plugin also uses, so
the CLI and the plugin produce identical output.

    mustrd run    --config my-mustrd-config.ttl [-v] [report options]
    mustrd report --config my-mustrd-config.ttl --term-coverage --cq --md report.md \\
                  --term-coverage-rdf run.ttl [--term-coverage-jsonld run.jsonld]
    mustrd report --config my-mustrd-config.ttl --viewer report.html

--config takes the same MustrdTest TTL as the pytest plugin's --config.
"""
import argparse
import sys
from pathlib import Path

import logging

from mustrd import logger_setup
from mustrd.reporting import (
    ReportOptions, wants_coverage, wants_cq, collect_cq_defs, produce_report,
)
from mustrd.runner import run_config, ontology_paths_from_config

log = logger_setup.setup_logger(__name__)


class _StdoutHandler(logging.StreamHandler):
    """A stream handler that resolves `sys.stdout` when it emits, not when it is
    constructed — so anything redirecting stdout afterwards (a pipe, a test's
    capture) still sees the output."""

    @property
    def stream(self):
        return sys.stdout

    @stream.setter
    def stream(self, _value):
        pass


def _configure_logging(verbose):
    """Make the library's own logging visible.

    mustrd.mustrd clears the root logger's handlers when it is imported (see
    debug_requests_off), which under pytest is harmless — pytest captures logging
    itself — but for the CLI it silently swallowed everything, including the whole
    result-review table. So attach a handler to the `mustrd` package logger and
    stop propagation there, rather than depend on the root logger's state.
    """
    package = logging.getLogger("mustrd")
    package.setLevel(logging.DEBUG if verbose else logging.INFO)
    if not any(getattr(h, "_mustrd_cli", False) for h in package.handlers):
        handler = _StdoutHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler._mustrd_cli = True
        package.addHandler(handler)
    package.propagate = False


def _add_report_options(parser):
    """Reporting flags shared by `run` and `report` — mirror the pytest plugin's
    options so the CLI and the plugin behave the same."""
    parser.add_argument("--md", dest="md_path", default=None,
                        help="Write the Markdown report to this path.")
    parser.add_argument("--term-coverage", action="store_true",
                        help="Compute and print ontology term coverage.")
    parser.add_argument("--cq", action="store_true",
                        help="Add the competency-questions report.")
    parser.add_argument("--term-coverage-rdf", default=None,
                        help="Write the coverage graph as Turtle to this path.")
    parser.add_argument("--term-coverage-jsonld", default=None,
                        help="Write the coverage graph as JSON-LD to this path "
                             "(for the standalone viewer).")
    parser.add_argument("--results-rdf", default=None,
                        help="Write per-test results (every test, passed/failed/"
                             "skipped, with timing) as RDF Turtle to this path.")
    parser.add_argument("--results-jsonld", default=None,
                        help="Write per-test results as JSON-LD to this path "
                             "(for the viewer's Playwright-style test tree).")
    parser.add_argument("--viewer", default=None, metavar="pathToHtml",
                        help="Write a self-contained HTML report to this path: one "
                             "file, no dependencies, with the run's RDF inlined and "
                             "rendered in the browser (tests, coverage, competency "
                             "questions, issues).")
    parser.add_argument("--viewer-title", default="mustrd run report",
                        help="Page title for --viewer.")
    parser.add_argument("--viewer-sources", action=argparse.BooleanOptionalAction,
                        default=True,
                        help="Inline each spec's Turtle and the SPARQL it ran into "
                             "the --viewer page, so the report is readable without "
                             "the files it was generated from (default: on). "
                             "--no-viewer-sources keeps the page smaller.")
    parser.add_argument("--viewer-src-base", default=None, metavar="prefix",
                        help="Prefix for the viewer's spec/ontology source links. "
                             "The graph stores paths relative to the working "
                             "directory, so set this when the page is served from "
                             "somewhere else (e.g. '../' for a report/ subdir). "
                             "Defaults to the GitHub blob URL in Actions.")
    parser.add_argument("--term-links", choices=("off", "file", "iri"), default="off",
                        help="How to linkify terms in the report.")
    parser.add_argument("--ontology", dest="ontology", action="append", default=None,
                        help="Ontology file/dir to measure against (repeatable). "
                             "Overrides mustrdTest:hasOntologyPath from the config.")


def _resolve_ontology_paths(args):
    if args.ontology:
        return tuple(args.ontology)
    return tuple(ontology_paths_from_config(args.config))


def _report_options(args) -> ReportOptions:
    return ReportOptions(
        md_path=args.md_path,
        term_coverage=args.term_coverage,
        cq=args.cq,
        term_coverage_rdf=args.term_coverage_rdf,
        term_coverage_jsonld=args.term_coverage_jsonld,
        results_rdf=args.results_rdf,
        results_jsonld=args.results_jsonld,
        viewer=args.viewer,
        viewer_title=args.viewer_title,
        viewer_src_base=args.viewer_src_base,
        viewer_sources=args.viewer_sources,
        term_links=args.term_links,
        ontology_paths=_resolve_ontology_paths(args),
    )


# The artifact options, paired with what to call them when reporting what was
# written. Order is the order they are listed in.
_ARTIFACTS = (
    ("viewer", "self-contained report"),
    ("md_path", "markdown report"),
    ("term_coverage_rdf", "coverage graph (Turtle)"),
    ("term_coverage_jsonld", "coverage graph (JSON-LD)"),
    ("results_rdf", "results graph (Turtle)"),
    ("results_jsonld", "results graph (JSON-LD)"),
)


def _report_written(opts: ReportOptions):
    """Say what was written, and where. A `report` run can otherwise succeed in
    complete silence, which reads like nothing happened."""
    for attr, label in _ARTIFACTS:
        path = getattr(opts, attr)
        if path and Path(path).exists():
            print(f"wrote {path} — {label}")


def _emit(args, review):
    """Run the config's specs and emit the requested reports. Returns the process
    exit code (non-zero if any spec did not pass)."""
    opts = _report_options(args)

    results, all_specs, spec_by_uri, test_results, run_results, spec_paths = run_config(
        args.config, secrets=args.secrets, ignore_focus=args.ignore_focus,
        verbose=args.verbose, review=review,
    )

    cq_defs = collect_cq_defs(spec_paths, spec_by_uri) if wants_cq(opts) else []

    produce_report(
        all_specs, cq_defs, test_results, True, opts,
        terminal_writer=lambda body: print(
            body or "No competency questions or ontology coverage to report."),
        run_results=run_results,
    )

    from mustrd.mustrd import SpecPassed, SpecPassedWithWarning
    failed = [r for r in results
              if not isinstance(r, (SpecPassed, SpecPassedWithWarning))]
    # `run` already prints the review table; `report` would otherwise say nothing.
    if not review:
        passed = len(results) - len(failed)
        print(f"{passed} passed, {len(failed)} not passed"
              f" ({len(results)} spec{'' if len(results) == 1 else 's'})")
    _report_written(opts)
    return 1 if failed else 0


def _cmd_run(args):
    # `run` defaults to no reporting flags -> just runs specs + review table.
    return _emit(args, review=True)


def _cmd_report(args):
    # `report` runs specs quietly and emits the report artifacts.
    opts = _report_options(args)
    if not (opts.md_path or wants_coverage(opts) or opts.cq or opts.viewer
            or opts.results_rdf or opts.results_jsonld):
        log.warning("Nothing to report: pass --viewer, --md, --term-coverage, --cq, "
                    "and/or --term-coverage-rdf / --term-coverage-jsonld / "
                    "--results-rdf / --results-jsonld.")
    return _emit(args, review=False)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="mustrd", description="Spec-By-Example for RDF & SPARQL.")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p):
        p.add_argument("-c", "--config", required=True,
                       help="Path to the MustrdTest configuration TTL.")
        p.add_argument("--secrets", default=None,
                       help="Secrets for triple-store connections (CI).")
        p.add_argument("--ignore-focus", dest="ignore_focus", action="store_true",
                       help="Ignore focus markers in specs.")
        p.add_argument("-v", "--verbose", action="store_true", help="Verbose logging.")

    p_run = sub.add_parser("run", help="Run the specs and review the results.")
    common(p_run)
    _add_report_options(p_run)
    p_run.set_defaults(func=_cmd_run)

    p_report = sub.add_parser("report", help="Run the specs and emit reports.")
    common(p_report)
    _add_report_options(p_report)
    p_report.set_defaults(func=_cmd_report)

    return parser


def _check_config(path):
    """Fail with a usage message, not an rdflib traceback, when --config is wrong.

    Getting the working directory wrong is the easiest mistake to make here: the
    paths inside a config are resolved relative to the config file, so it is
    tempting to run from the wrong place."""
    config = Path(path)
    if config.is_dir():
        raise SystemExit(f"mustrd: --config must be a MustrdTest TTL file, but "
                         f"{path} is a directory.")
    if not config.is_file():
        raise SystemExit(
            f"mustrd: no such configuration file: {path}\n"
            f"  Looked in: {config.resolve().parent}\n"
            "  --config takes the path to a MustrdTest TTL (the same file the "
            "pytest plugin's --config takes)."
        )


def main(argv=None):
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    _check_config(args.config)
    _configure_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
