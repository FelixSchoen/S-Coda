import logging
import logging.config

from scoda.settings import ROOT_LOGGER

initial_call = True


def get_logger(name):
    # Check if this is the first logger on this thread
    global initial_call

    if initial_call:
        setup_root_logger()
        initial_call = False

    logger = logging.getLogger(ROOT_LOGGER + "." + name)

    return logger


def setup_root_logger():
    root_logger = logging.getLogger(ROOT_LOGGER)
    root_logger.setLevel(logging.WARNING)
    root_logger.propagate = False

    handler = logging.StreamHandler()
    handler.setLevel(logging.WARNING)

    formatter = logging.Formatter("%(asctime)s - [%(name)s] - %(levelname)s: %(message)s")
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)
