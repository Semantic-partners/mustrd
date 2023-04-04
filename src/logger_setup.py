import logging
import sys
from colorlog import ColoredFormatter


LOG_LEVEL = logging.INFO
LOG_FORMAT = '%(log_color)s%(levelname)s:%(name)s:%(white)s%(message)s'


# Set up the logger
def setup_logger(name):
    log = logging.getLogger(name)
    log.setLevel(LOG_LEVEL)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(LOG_LEVEL)
    ch.setFormatter(ColoredFormatter(LOG_FORMAT))
    log.addHandler(ch)

    return log


# Define a function to flush the logger and stdout
def flush():
    logging.shutdown()
    sys.stdout.flush()