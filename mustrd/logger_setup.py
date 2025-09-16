import logging
import sys
from colorlog import ColoredFormatter


LOG_LEVEL = logging.INFO
LOG_FORMAT = '%(log_color)s%(levelname)s:%(name)s:%(white)s%(message)s'


def setup_logger(name: str) -> logging.Logger:
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

logging.getLogger("edn_format").setLevel(logging.WARNING)
