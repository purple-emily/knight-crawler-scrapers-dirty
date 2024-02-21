import argparse
import asyncio
import sys

from loguru import logger

from scrapers.eztv.scraper import get_list_of_shows_from_eztv
from scrapers.util.showlist import ShowList

# TRACE       5
# DEBUG      10
# INFO       20
# SUCCESS    25
# WARNING    30
# ERROR      40
# CRITICAL   50
logger_level = "INFO"


def logger_level_filter(record):  # type: ignore
    return record["level"].no >= logger.level(logger_level).no  # type: ignore


logger.remove()
logger.add(sys.stderr, filter=logger_level_filter)  # type: ignore


async def main(eztv_showlist_file: str) -> None:
    eztv_showlist: ShowList = ShowList()
    await eztv_showlist.load_from_file(eztv_showlist_file)
    await get_list_of_shows_from_eztv(eztv_showlist)
    await eztv_showlist.save_to_file(eztv_showlist_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="I am bad at descriptions.")
    parser.add_argument(
        "--eztv-showlist-file",
        "-e",
        default="eztv_showlist.json",
        help="Defaults to 'eztv_showlist.json' in the root directory.",
    )
    args = parser.parse_args()
    asyncio.run(main(args.eztv_showlist_file))
