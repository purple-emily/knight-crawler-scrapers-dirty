import asyncio
import contextlib
import re
from collections import Counter
from itertools import batched
from pathlib import Path

import httpx
import pydantic
from aiolimiter import AsyncLimiter
from arrow import Arrow
from loguru import logger
from lxml import html

from scrapers.config import config
from scrapers.models.media import Media
from scrapers.models.media_collection import MediaCollection
from scrapers.utility.message_queue import RabbitInterface


async def eztv_scraper(data_directory: Path, rabbit_interface: RabbitInterface) -> None:
    logger.info("Starting EZTV scraper")

    eztv_collection: MediaCollection = await MediaCollection.load_from_file(
        "eztv", data_directory
    )
    collection_lock = asyncio.Lock()

    http_rate_limit: AsyncLimiter = AsyncLimiter(config.rate_limit_per_second, 1)

    # If the EZTV showlist is more than 4 hours out of date or no data exists
    if await eztv_collection.is_expired(collection_lock):
        await get_list_of_shows(eztv_collection, collection_lock, http_rate_limit)
        await eztv_collection.save_to_file("eztv", collection_lock)

    missing_imdb_ids: list[str] = await eztv_collection.missing_imdbs(collection_lock)
    if len(missing_imdb_ids) > 0:
        logger.debug(
            f"Beginning search for {len(missing_imdb_ids)} IMDB id's. This may take a while..."
        )
        # Split the missing_imdb_ids into smaller batches. This minimises data loss if
        # the program to crash or the user to quits the program in the middle of the process
        total_number_of_batches = len(
            list(batched(missing_imdb_ids, config.batch_size))
        )

        async with httpx.AsyncClient() as httpx_client:
            for loop_number, urls in enumerate(
                batched(missing_imdb_ids, config.batch_size), 1
            ):
                found_imdbs = await asyncio.gather(
                    *(find_imdb_id(url, httpx_client, http_rate_limit) for url in urls)
                )

                found_count = sum(isinstance(item, dict) for item in found_imdbs)

                for value in found_imdbs:
                    if value is None:
                        continue

                    for url, imdb in value.items():
                        media = await eztv_collection.get_media(url, collection_lock)

                        with contextlib.suppress(pydantic.ValidationError):
                            media.imdb = imdb

                        await eztv_collection.update_media(media, collection_lock)

                percentage_done = (loop_number / total_number_of_batches) * 100
                logger.debug(
                    f"IMDB id progress: {percentage_done:.2f}%. Batch success: {found_count}/{config.batch_size}"
                )
                await eztv_collection.save_to_file("eztv", collection_lock)

    logger.debug(rabbit_interface)

    # # Showlist is now updated. Proceed with normal code
    # for url, media in eztv_collection.collection.items():
    #     pass


async def find_imdb_id(
    url: str, httpx_client: httpx.AsyncClient, http_rate_limit: AsyncLimiter
) -> dict[str, str] | None:
    async with http_rate_limit:
        try:
            response = await httpx_client.get(f"{url}")
            html_response = response.text
        except httpx.HTTPError as exc:
            logger.exception(exc)
            return None

    try:
        imdb_regex: re.Match["str"] | None = re.search(
            r"https://www.imdb.com/title/(tt[0-9]+)/", html_response
        )
    except AttributeError:
        return None

    if imdb_regex is None:
        return None

    found_imdb: str = imdb_regex.group(1)

    return {url: found_imdb}


async def get_list_of_shows(
    eztv_collection: MediaCollection,
    collection_lock: asyncio.Lock,
    http_rate_limit: AsyncLimiter,
) -> None:
    logger.info("Pulling new list of shows from EZTV")

    # Update the EZTV showlist
    eztv_showlist_url = f"{config.eztv_base_url}{config.eztv_showlist_route}"
    async with httpx.AsyncClient() as httpx_client, http_rate_limit:
        response = await httpx_client.get(eztv_showlist_url)
        # If we have anything other than a 200 response, cancel scraping
        if response.status_code != 200:  # noqa: PLR2004
            logger.error(
                f"There was an error accessing EZTV. Error code: {response.status_code}"
            )
            return
        html_response: str = response.text

    lxml_html_tree: list[html.HtmlElement] = html.fromstring(html_response).xpath(  # type: ignore
        '//tr[@name="hover"]'
    )

    async def process_lxml_html_element(
        lxml_html_element: html.HtmlElement,
        eztv_collection: MediaCollection,
        collection_lock: asyncio.Lock,
    ) -> int:
        # 0 = no change
        # 1 = updated
        # 2 = new
        # 3 = error
        try:
            _first_element: html.HtmlElement = lxml_html_element.xpath(  # type: ignore
                ".//td[@class='forum_thread_post']/a"
            )[0]
            url: str = f"{config.eztv_base_url}{_first_element.get('href')}"  # type: ignore

            title: str = _first_element.text_content()  # type: ignore

            _second_element: html.HtmlElement = lxml_html_element.xpath(  # type: ignore
                ".//td[@class='forum_thread_post']/font"
            )[0]
            status: str = _second_element.text.strip()  # type: ignore

            media: Media = Media(url=url, title=title, type="tv", status=status)  # type: ignore
        except pydantic.ValidationError:
            return 3

        if await eztv_collection.add_media(media, collection_lock):
            return 2

        try:
            if await eztv_collection.update_media(media, collection_lock):
                return 1
        except KeyError:
            return 3

        return 0

    found_media_response: list[int] = await asyncio.gather(
        *(
            process_lxml_html_element(html_element, eztv_collection, collection_lock)  # type: ignore
            for html_element in lxml_html_tree  # type: ignore
        )
    )

    logger.debug(f"{len(found_media_response)} EZTV shows found")
    # 0 = no change
    # 1 = updated
    # 2 = new
    # 3 = error
    responses_count = dict(Counter(found_media_response))
    logger.debug(f"EZTV: {responses_count.get(2, 0)} new")
    logger.debug(f"EZTV: {responses_count.get(1, 0)} updated")
    logger.debug(f"EZTV: {responses_count.get(0, 0)} unchanged")
    logger.debug(f"EZTV: {responses_count.get(3, 0)} errors")

    async with collection_lock:
        eztv_collection.last_updated = Arrow.utcnow().datetime
