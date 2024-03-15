import asyncio
from pathlib import Path

from scrapers.config import config
from scrapers.scrapers.eztv import eztv_scraper
from scrapers.utility.message_queue import RabbitInterface


async def start_producer(data_directory: Path, scrape_eztv: bool) -> None:
    # Convert the data directory to a Path object
    # if the directory doesn't exist, offer to create it
    # then either quit when permission not given
    # or try to create dir when permission given
    active_scrapers = []
    async with await RabbitInterface.create(
        rabbit_uri=config.rabbit_uri
    ) as rabbit_interface:
        if scrape_eztv:
            eztv_task = asyncio.create_task(  # type: ignore
                eztv_scraper(data_directory, rabbit_interface)
            )
            active_scrapers.append(eztv_task)  # type: ignore

        await asyncio.gather(*active_scrapers)  # type: ignore
