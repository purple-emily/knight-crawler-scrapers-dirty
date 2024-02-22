import sys

from loguru import logger

from scrapers.util.config import config


def init(desired_log_level: str):
    valid_log_levels = [
        "TRACE",
        "DEBUG",
        "INFO",
        "SUCCESS",
        "WARNING",
        "ERROR",
        "CRITICAL",
    ]

    desired_log_level = desired_log_level.upper()

    if desired_log_level not in valid_log_levels:
        desired_log_level = "INFO"

    logger.remove()
    logger.add(sys.stderr, level=desired_log_level)
    if config.debug_mode:
        logger.add("debug.log", mode="w", level="DEBUG")
