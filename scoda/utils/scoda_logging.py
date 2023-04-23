import logging
import logging.config

from scoda.settings.settings import LOGGER_ROOT_NAME

initial_call = True


def get_logger(name):
    # Check if this is the first logger on this thread
    global initial_call

    if initial_call:
        setup_root_logger()
        initial_call = False

    logger = logging.getLogger(LOGGER_ROOT_NAME + "." + name)

    return logger


def setup_root_logger():
    root_logger = logging.getLogger(LOGGER_ROOT_NAME)
    root_logger.setLevel(logging.WARNING)
    root_logger.propagate = False

    handler = logging.StreamHandler()
    handler.setLevel(logging.WARNING)

    formatter = logging.Formatter("%(asctime)s - [%(name)s] - %(levelname)s: %(message)s")
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)
