import logging
import logging.config
from pathlib import Path

logger: logging.Logger = None


def setup_logger(logger_designation: str = None) -> logging.Logger:
    return _setup_logger(logger_designation)


def _setup_logger(logger_designation: str) -> logging.Logger:
    if logger_designation is None:
        logger_designation = "scoda"

    global logger

    if logger is None:
        logging.config.fileConfig(Path(__file__).parent.parent.joinpath("config/logging.conf"))
        logger = logging.getLogger(logger_designation)

    return logger
