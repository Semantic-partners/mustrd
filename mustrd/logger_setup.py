"""The one place mustrd configures logging — and only when mustrd is the application.

The rule, applied throughout the package:

  - Library modules do `log = logging.getLogger(__name__)` and nothing else.
    Importing mustrd must never add, remove or re-level a handler: whoever
    imported it owns that decision, and silently replacing their configuration is
    exactly the bug this module exists to avoid.
  - The application configures. The `mustrd` CLI calls `configure()`. Under
    pytest, *pytest* is the application, so the plugin configures nothing and
    `--log-cli-level` behaves as documented.

`setup_logger` is the older per-logger variant, kept for existing callers.
Prefer `configure()`.
"""
import logging
import sys

from colorlog import ColoredFormatter

LOG_LEVEL = logging.INFO
LOG_FORMAT = '%(log_color)s%(levelname)s:%(name)s:%(white)s%(message)s'

# Third-party loggers that are noisy at INFO and say nothing a mustrd user wants.
QUIET = ("edn_format",)


class _CliFormatter(logging.Formatter):
    """Bare messages at INFO, a level prefix above it.

    mustrd's INFO output is human-facing report content — result tables, coverage
    summaries — which `INFO:mustrd.mustrd:` in front of every line only makes
    harder to read. Anything unusual still announces itself."""

    def format(self, record):
        message = record.getMessage()
        if record.levelno <= logging.INFO:
            return message
        return f"{record.levelname}: {message}"


class _StdoutHandler(logging.StreamHandler):
    """Resolves `sys.stdout` when it emits rather than when it is constructed, so
    later redirection — a pipe, a test's capture — is still honoured."""

    @property
    def stream(self):
        return sys.stdout

    @stream.setter
    def stream(self, _value):
        pass


def configure(verbose: bool = False, formatter: logging.Formatter = None) -> logging.Logger:
    """Send mustrd's log records to stdout. Call from an entry point only.

    Attaches one handler to the `mustrd` package logger — not the root logger, so
    an embedding application's configuration is untouched — and stops propagation
    there, so records are not emitted twice. Idempotent.
    """
    package = logging.getLogger("mustrd")
    package.setLevel(logging.DEBUG if verbose else LOG_LEVEL)
    if not any(getattr(handler, "_mustrd", False) for handler in package.handlers):
        handler = _StdoutHandler()
        handler.setFormatter(formatter or _CliFormatter())
        handler._mustrd = True
        package.addHandler(handler)
    package.propagate = False
    for name in QUIET:
        logging.getLogger(name).setLevel(logging.WARNING)
    return package


def setup_logger(name: str) -> logging.Logger:
    """Configure one named logger: colour on stdout, errors also on stderr.

    Predates `configure()`. It mutates the named logger's handlers, so it belongs
    in an entry point — never call it at import time from a library module.
    """
    log = logging.getLogger(name)
    log.setLevel(LOG_LEVEL)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.ERROR)
    log.addHandler(stderr_handler)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(LOG_LEVEL)
    ch.setFormatter(ColoredFormatter(LOG_FORMAT))
    log.addHandler(ch)

    return log


def flush():
    logging.shutdown()
    sys.stdout.flush()
