import asyncio
import itertools
import json
import re
from datetime import timedelta

import arrow
import httpx
from aiolimiter import AsyncLimiter
from loguru import logger
from lxml import html

from scrapers.util.config import config
from scrapers.util.show import Show
from scrapers.util.showlist import ShowList
from scrapers.util.util import readable_timedelta


async def html_to_show(html) -> Show:
    url_element = html.xpath(".//td[@class='forum_thread_post']/a")[0]
    url = url_element.get("href")
    show_name = url_element.text_content()
    status_element = html.xpath(".//td[@class='forum_thread_post']/font")[0]
    status = status_element.text.strip()

    return Show(url=url, name=show_name, status=status)


async def add_imdbid_to_show(show: Show, rate_limit, client):
    async with rate_limit:
        try:
            response = await client.get(f"{config.eztv_url}{show.url}")
            html_response = response.text

            imdb_regex_pattern = r"https://www.imdb.com/title/tt([0-9]+)/"
            try:
                imdb_id = re.search(imdb_regex_pattern, html_response).group(1)
            except AttributeError:
                imdb_id = None
            logger.debug(f"Found IMDb ID: `{imdb_id}` for show: `{show.name}`")
            show.imdbid = imdb_id
        except httpx.HTTPError as e:
            logger.exception(e)
            logger.error(
                f"There appears to be an error accessing EZTV at the URL `{config.eztv_url}{show.url}"
            )
            logger.error(
                "The script will attempt to continue, but please can you post the logs in Discord and tag @TheBestEmily"
            )


async def get_all_imdbids(showlist: ShowList, eztv_showlist_file):
    shows_without_imdbid = showlist.get_shows_with_no_imdbid()

    if len(shows_without_imdbid) == 0:
        logger.info("No shows need an IMDb update!")
        return

    # Limit the processing limit for debugging
    if config.debug_mode:
        logger.debug(
            f"Debug mode enabled. Limiting to {config.debug_processing_limit} updates"
        )
        shows_without_imdbid = shows_without_imdbid[0 : config.debug_processing_limit]

    logger.info(
        f"{len(shows_without_imdbid)} shows are missing an IMDb ID. Trying to get IMDb IDs, this may take a while..."
    )

    rate_limit = AsyncLimiter(config.rate_limit_per_second, 1)

    total_number_of_batches = len(
        list(itertools.batched(shows_without_imdbid, config.batch_size))
    )

    for batch_number, batch_of_shows in enumerate(
        itertools.batched(shows_without_imdbid, config.batch_size), 1
    ):
        async with httpx.AsyncClient() as client:
            await asyncio.gather(
                *(
                    add_imdbid_to_show(show, rate_limit, client)
                    for show in batch_of_shows
                )
            )

        await asyncio.gather(
            *(
                showlist.update_show_imdbid(show.url, imdbid=show.imdbid)
                for show in shows_without_imdbid
            )
        )

        await showlist.save_to_file(eztv_showlist_file)

        percentage_done = (batch_number / total_number_of_batches) * 100
        logger.info(f"Progress: {percentage_done:.2f}% / 100%")


async def get_list_of_shows(showlist: ShowList, eztv_showlist_file: str):
    current_time = arrow.now()
    time_difference = current_time - showlist.timestamp
    max_age = timedelta(hours=4)

    logger.info(
        f"Showlist is `{readable_timedelta(time_difference)}` old. Max configured age is {readable_timedelta(max_age)}"
    )

    if time_difference > max_age:
        showlist_url = f"{config.eztv_url}{config.eztv_showlist_url}"
        logger.info(f"Updating showlist from `{showlist_url}`")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(showlist_url)
                html_response = response.text
            # except json.decoder.JSONDecodeError:
            #     raise

            tree = html.fromstring(html_response)

            updated_showlist = await asyncio.gather(
                *(
                    html_to_show(show_html)
                    for show_html in tree.xpath('//tr[@name="hover"]')
                )
            )

            number_of_new_shows = 0
            number_of_updated_shows = 0
            for show in updated_showlist:
                # Try to add the show to our current showlist.
                # If it succeeds, the show is new.
                # If it fails we already have this show in our list, but we can update the
                # `status` of the show without any additional GET requests.
                if await showlist.add_show(show):
                    logger.info(
                        f"Found a new show: `{show.name}` ({number_of_new_shows} new shows so far)"
                    )
                    number_of_new_shows += 1
                else:
                    if await showlist.update_show_status(show.url, status=show.status):
                        logger.debug(
                            f"Show `{show.name}` status was updated to: `{show.status}`"
                        )
                        number_of_updated_shows += 1

            logger.info(f"Total number of new shows found: {number_of_new_shows}")
            logger.info(
                f"Total number of shows updated with a new status: {number_of_updated_shows}"
            )

            await showlist.reset_timestamp()
        except httpx.HTTPError as e:
            logger.exception(e)
            logger.error(
                f"There appears to be an error accessing EZTV at the URL `{showlist_url}`"
            )
            logger.error(
                "The script will attempt to continue, but please can you post the logs in Discord and tag @TheBestEmily"
            )

    await get_all_imdbids(showlist, eztv_showlist_file)


async def get_api_data(show: Show, rate_limit, client):
    async with rate_limit:
        # https://eztvx.to/api/get-torrents?imdb_id=6048596
        try:
            response = await client.get(
                f"{config.eztv_url}/api/get-torrents?imdb_id={show.imdbid}"
            )
            return response.json()
        except json.decoder.JSONDecodeError:
            raise
        except httpx.HTTPError:
            raise
