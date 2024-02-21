import asyncio
import re

import httpx
from aiolimiter import AsyncLimiter
from loguru import logger
from lxml import html

from scrapers.util.config import config
from scrapers.util.show import Show
from scrapers.util.showlist import ShowList


async def html_to_show(html) -> Show:
    url_element = html.xpath(".//td[@class='forum_thread_post']/a")[0]
    url = url_element.get("href")
    show_name = url_element.text_content()
    status_element = html.xpath(".//td[@class='forum_thread_post']/font")[0]
    status = status_element.text.strip()

    return Show(url=url, name=show_name, status=status)


async def add_imdbid_to_show(show: Show, rate_limit, client):
    async with rate_limit:
        response = await client.get(f"{config.eztv_url}{show.url}")
        html_response = response.text

        imdb_regex_pattern = r"https://www.imdb.com/title/tt([0-9]+)/"
        try:
            imdb_id = re.search(imdb_regex_pattern, html_response).group(1)
        except AttributeError:
            imdb_id = None

        show.imdbid = imdb_id


async def get_list_of_shows_from_eztv(showlist: ShowList):
    showlist_url = f"{config.eztv_url}{config.eztv_showlist_url}"
    logger.info(f"Pulling showlist from `{showlist_url}`")

    async with httpx.AsyncClient() as client:
        response = await client.get(showlist_url)
        html_response = response.text

    tree = html.fromstring(html_response)

    updated_showlist = await asyncio.gather(
        *(html_to_show(show_html) for show_html in tree.xpath('//tr[@name="hover"]'))
    )

    new_show_count = 0
    for show in updated_showlist:
        if not await showlist.add_show(show):
            logger.debug(f"Updating airing status {show=}")
            await showlist.update_show(show.url, show.status)
        else:
            logger.debug(f"New show {show=}")
            new_show_count += 1
    logger.info(f"Found {new_show_count} new shows")

    shows_without_imdbid = showlist.get_shows_with_no_imdbid()
    if config.debug_mode:
        logger.debug(
            f"Debug mode enabled. Limiting to {config.debug_processing_limit} updates"
        )
        shows_without_imdbid = shows_without_imdbid[0 : config.debug_processing_limit]
    logger.info(
        f"{len(shows_without_imdbid)} shows are missing an IMDb ID. Trying to get IMDb IDs, this may take a while..."
    )
    rate_limit = AsyncLimiter(config.rate_limit_per_second, 1)
    async with httpx.AsyncClient() as client:
        await asyncio.gather(
            *(
                add_imdbid_to_show(show, rate_limit, client)
                for show in shows_without_imdbid
            )
        )

    await asyncio.gather(
        *(showlist.update_show(show.url, show.imdbid) for show in shows_without_imdbid)
    )
    # Update the IMDb ID's only for now, not the show status
    # for show in shows_without_imdbid:
    #     pass

    # At this point we have `url`, `show_name` and `status`.
    # Missing the IMDb id
