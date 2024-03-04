import sys

from loguru import logger

from scrapers.config import config


def init(desired_log_level: str, process: str):
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
        desired_log_level = "DEBUG"

    logger.remove()
    logger.add(sys.stderr, level=desired_log_level)
    if config.debug_mode:
        if process == "consumer":
            logger.add("debug_consumer_{time}.log", mode="w", level="DEBUG")
        elif process == "producer":
            logger.add("debug_producer_{time}.log", mode="w", level="DEBUG")
