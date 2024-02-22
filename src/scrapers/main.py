import argparse
import asyncio

from scrapers import logging
from scrapers.scrapers import eztv
from scrapers.services import knightcrawler
from scrapers.util.showlist import ShowList


async def main(eztv_showlist_file: str, log_level: str) -> None:
    # Set the user log level
    logging.init(log_level)

    eztv_showlist: ShowList = ShowList()
    await eztv_showlist.load_from_file(eztv_showlist_file)
    await eztv.get_list_of_shows(eztv_showlist, eztv_showlist_file)
    await eztv_showlist.save_to_file(eztv_showlist_file)

    await knightcrawler.scrape_eztv(eztv_showlist)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="I am bad at descriptions.")
    parser.add_argument(
        "--eztv-showlist-file",
        "-e",
        default="eztv_showlist.json",
        help="Defaults to 'eztv_showlist.json' in the root directory.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Defaults to 'INFO'. Warning `DEBUG` is very verbose.",
    )
    # parser.add_argument(
    #     "--debug",
    #     default=False,
    #     help="Defaults to 'INFO'. Warning `DEBUG` is very verbose.",
    # )
    args = parser.parse_args()
    asyncio.run(main(args.eztv_showlist_file, args.log_level))
