import argparse
import asyncio

from scrapers import logging
from scrapers.scrapers import eztv
from scrapers.services import knightcrawler
from scrapers.util.showlist import ShowList


async def main(role: str, eztv_showlist_file: str, log_level: str) -> None:
    # Set the user log level
    logging.init(log_level, role)

    eztv_showlist: ShowList = ShowList()
    await eztv_showlist.load_from_file(eztv_showlist_file)
    await eztv.get_list_of_shows(eztv_showlist, eztv_showlist_file)
    await eztv_showlist.save_to_file(eztv_showlist_file)

    if role == "producer":
        await knightcrawler.scrape_eztv(eztv_showlist, loop)
    elif role == "consumer":
        await knightcrawler.consume_eztv(eztv_showlist, loop)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="I am bad at descriptions.")
    parser.add_argument("role")
    parser.add_argument(
        "--eztv-showlist-file",
        "-e",
        default="eztv_showlist.json",
        help="Defaults to 'eztv_showlist.json' in the root directory.",
    )
    parser.add_argument(
        "--log-level",
        default="DEBUG",
        help="Defaults to 'INFO'. Warning `DEBUG` is very verbose.",
    )
    # parser.add_argument(
    #     "--debug",
    #     default=False,
    #     help="Defaults to 'INFO'. Warning `DEBUG` is very verbose.",
    # )
    args = parser.parse_args()
    loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
    loop.run_until_complete(main(args.role, args.eztv_showlist_file, args.log_level))
    loop.close()
