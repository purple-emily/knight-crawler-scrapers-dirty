import argparse
import asyncio
import datetime
import json
import os
import re
from datetime import timedelta

import aiofiles
import arrow
import asyncpg
import httpx
import redis
from aiolimiter import AsyncLimiter
from loguru import logger
from lxml import html

from scrapers.util import config

redis_pool = redis.ConnectionPool(
    host=os.getenv("REDIS_HOST"),
    port=os.getenv("REDIS_PORT"),
    db=os.getenv("REDIS_DB"),
    password=os.getenv("REDIS_PASSWORD"),
)


async def create_postgres_tables(
    ingested_torrents_table: str, eztv_ingested_pages_table: str
) -> None:
    conn = await asyncpg.connect(
        user=config.postgres_user,
        password=config.postgres_password,
        database=config.postgres_db,
        host=config.postgres_host,
        port=config.postgres_port,
    )
    try:
        if config.debug_mode:
            logger.debug(
                f"Creating postgres table `{ingested_torrents_table}` if it does not exist"
            )
            await conn.execute(
                f"""CREATE TABLE IF NOT EXISTS {ingested_torrents_table} (
                        id SERIAL PRIMARY KEY,
                        name character varying(255),
                        source character varying(255),
                        category character varying(255),
                        info_hash character varying(255),
                        size character varying(255),
                        seeders integer,
                        leechers integer,
                        imdb character varying(255),
                        processed boolean DEFAULT false,
                        "createdAt" timestamp with time zone NOT NULL,
                        "updatedAt" timestamp with time zone NOT NULL
                    );
                """
            )
        logger.debug(
            f"Creating postgres table `{eztv_ingested_pages_table}` if it does not exist"
        )
        await conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {eztv_ingested_pages_table} (
                    id SERIAL PRIMARY KEY,
                    url character varying(255) NOT NULL,
                    showName character varying(255) NOT NULL,
                    status character varying(255) NOT NULL,
                    imdb character varying(255),
                    "createdAt" timestamp with time zone NOT NULL,
                    "updatedAt" timestamp with time zone NOT NULL
                );
            """
        )
    finally:
        await conn.close()


async def update_raw_showlist():
    if not config.eztv_url:
        raise ValueError("EZTV url is not configured. Please check the `.env` file.")

    eztv_showlist_url = f"{config.eztv_url}/showlist/"
    logger.info(f"Pulling showlist from `{eztv_showlist_url}`.")

    async with httpx.AsyncClient() as client:
        response = await client.get(eztv_showlist_url)
        html_response = response.text

    tree = html.fromstring(html_response)
    showlist = []
    rows = tree.xpath('//tr[@name="hover"]')
    for row in rows:
        url_element = row.xpath(".//td[@class='forum_thread_post']/a")[0]
        url = url_element.get("href")
        show_name = url_element.text_content()
        status_element = row.xpath(".//td[@class='forum_thread_post']/font")[0]
        status = status_element.text.strip()
        showlist.append(
            {"url": f"{config.eztv_url}{url}", "show_name": show_name, "status": status}
        )

    return showlist


async def showlist_to_showdict(showlist):
    async def add_imdbid_to_show(show: dict, showdict: dict, rate_limit, client):
        async with rate_limit:
            response = await client.get(show["url"])
            html_response = response.text

            imdb_regex_pattern = r"https://www.imdb.com/title/tt([0-9]+)/"
            try:
                imdb_id = re.search(imdb_regex_pattern, html_response).group(1)
            except AttributeError:
                imdb_id = None

            showdict[imdb_id] = show

    rate_limit = AsyncLimiter(config.rate_limit_per_second, 1)
    logger.info(
        f"Adding IMDb id to {len(showlist)} shows. This may take up to 10 minutes, please wait."
    )

    showdict = {}

    async with httpx.AsyncClient() as client:
        await asyncio.gather(
            add_imdbid_to_show(show, showdict, rate_limit, client) for show in showlist
        )
    return showdict


async def write_json(file, showdict):
    data = {
        "timestamp": arrow.now().isoformat(),
        "showdict": showdict,
    }

    async with aiofiles.open(file, "w", encoding="utf-8") as json_file:
        await json_file.write(json.dumps(data))


async def get_eztv_showlist(eztv_showlist_file: str, get_new_showlist: bool) -> list:
    """
    Get a list of shows that are available for download on EZTV

    Args:
        eztv_showlist_file (str): Cache file so we don't have to continuously request a new showlist
        get_new_showlist (bool): Force a showlist update
        debug_mode (bool, optional): Defaults to False

    Raises:
        ValueError: `EZTV_URL` is not configured in the .env file (only when updating showlist)

    Returns:
        list: List of shows that are available on EZTV (as URLs)
    """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Pseudo code:
    # if the showlist file doesn't exist then we can immediately just grab a new one
    # if the user requests an update, we don't need to hammer the eztv website for all of the data again, we just need to find differences and update those
    # return the data
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    # Fix the path to the showlist file
    # Before:
    #     showlist_file='showlist.json'
    # After:
    #     showlist_file='D:\\Development\\scrapers\\showlist.json'
    if not os.path.isabs(eztv_showlist_file):
        eztv_showlist_file = os.path.join(os.getcwd(), eztv_showlist_file)

    # Check if the showlist file does not exist
    if not os.path.exists(eztv_showlist_file):
        # The showlist file doesn't exist, so we will need to generate a new one. This is very hard on the EZTV server,
        # but I have attempted to rate limit it.
        showlist = await update_raw_showlist()

        if config.debug_mode:
            logger.debug(
                f"Debug mode enabled, limiting raw_showlist to {config.debug_processing_limit}"
            )
            showlist = showlist[0 : config.debug_processing_limit]

        showdict = await showlist_to_showdict(showlist)

        await write_json(eztv_showlist_file, showdict)

    # Check if the showlist file exists
    else:
        # The file exists, so we are going to load the data from it
        logger.debug(f"Loading saved showlist `{eztv_showlist_file}`")
        async with aiofiles.open(eztv_showlist_file, "r") as json_file:
            data = json.loads(await json_file.read())
            showdict = data["showdict"]

        # Get the timestamp from the JSON file
        timestamp = arrow.get(data["timestamp"])

        # Compare and warn if necessary
        current_time = arrow.now()
        time_difference = current_time - timestamp
        max_age = timedelta(days=7)

        if get_new_showlist or (time_difference > max_age):
            if get_new_showlist:
                logger.info("Received flag `--get-new-showlist`. Updating showlist.")
            elif time_difference > max_age:
                logger.info("Showlist data is outdated. Updating showlist.")

            showlist = await update_raw_showlist()
            # new_or_invalid_shows
            # This should check the loaded data `showlist_with_full_data` and compare it to the new raw_showlist
            # If the url in raw_showlist doesn't exist as a key in `showlist_with_full_data` we add it to `new_or_invalid_shows`
            # If the url is in `showlist_with_full_data` but the value is None we add it to `new_or_invalid_shows`
            # json examples:
            # "https://eztvx.to/shows/449713/textmewhenyougethome/": "tt19552690",
            # "https://eztvx.to/shows/482/5-inch-floppy/": null,
            new_or_invalid_shows = [
                show
                for imdbid, showdata in showdict.items()
                if showdata is None or showdata.get("imdb_id") not in showdict
            ]

            logger.info(f"{len(new_or_invalid_shows)} shows require updating.")

            updated_shows = await showlist_to_showdict(new_or_invalid_shows)

            for imdb_id, data in updated_shows.items():
                showdict[imdb_id] = {
                    "show_name": data["show_name"],
                    "status": data["status"],
                    "url": data["url"],
                }

            await write_json(eztv_showlist_file, showdict)

    logger.debug(f"The showlist contains {len(showdict)} series")
    return showdict


async def get_showlist_api_data(show_queue, showlist):
    async def get_show_api_data(show_queue, show: dict, rate_limit, client):
        async with rate_limit:
            logger.debug(f"{type(show)}")
            exit()
            imdbid, show_data = show.values()
            response = await client.get(show_data["url"])
            show[imdbid]["api_json"] = response.json()

            await show_queue.put(show)

    rate_limit = AsyncLimiter(config.rate_limit_per_second, 1)

    logger.info(
        f"Getting API data for {len(showlist)} shows. This may take up to 10 minutes, please wait."
    )
    async with httpx.AsyncClient() as client:
        await asyncio.gather(
            *(
                get_show_api_data(show_queue, show, rate_limit, client)
                for show in showlist
            )
        )

    await show_queue.put(None)


async def add_show_to_postgres(
    show, ingested_torrents_table, eztv_ingested_pages_table
):
    if config.debug_mode:
        redis_expire_time_seconds = 15
    else:
        redis_expire_time_seconds = 3600

    conn = await asyncpg.connect(
        user=config.postgres_user,
        password=config.postgres_password,
        database=config.postgres_db,
        host=config.postgres_host,
        port=config.postgres_port,
    )

    try:
        torrents = []

        for torrent in show["api_json"]["torrents"]:
            title = torrent["title"]
            info_hash = torrent["hash"]
            size = int(torrent["size_bytes"])
            seeders = torrent["seeds"]
            leechers = torrent["peers"]
            created_at = datetime.datetime.now()
            updated_at = created_at

            exists_query = f"""
            SELECT EXISTS (
                SELECT 1
                FROM {ingested_torrents_table}
                WHERE info_hash = $1 AND source = $2
            );
            """
            exists = await conn.fetchval(exists_query, info_hash, "EZTV-py")

            if exists:
                continue  # Skip processing if already in Postgres

            new_torrent = [
                title,
                "EZTV-py",
                "tv",
                info_hash,
                f"{size}",
                seeders,
                leechers,
                None,
                False,
                created_at,
                updated_at,
            ]
            torrents.append(new_torrent)

        # Insert data into the database
        logger.info(
            f"Processing {len(torrents)} torrents for series `{show["imdb_id"]}`"
        )
        await conn.executemany(
            f"""INSERT INTO {ingested_torrents_table} (name, source, category, info_hash, size, seeders, leechers, imdb, processed, "createdAt", "updatedAt")
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)""",
            torrents,
        )

        await conn.execute(
            f"""INSERT INTO {eztv_ingested_pages_table} (url, showName, status, imdb, "createdAt", "updatedAt")
                VALUES ($1, $2, $3, $4, $5)""",
            show["url"],
        )

    # {
    #   "1187505": {
    #     "url": "https://eztvx.to/shows/69006/10-years-younger-in-10-days/",
    #     "show_name": "10 Years Younger in 10 Days",
    #     "status": "Pending"
    #   }
    # }

    # f"""CREATE TABLE IF NOT EXISTS {eztv_ingested_pages_table} (
    #         id SERIAL PRIMARY KEY,
    #         url character varying(255) NOT NULL,
    #         showName character varying(255) NOT NULL,
    #         status character varying(255) NOT NULL,
    #         "createdAt" timestamp with time zone NOT NULL,
    #         "updatedAt" timestamp with time zone NOT NULL
    #     );
    # """

    # await conn.execute(
    #     f"""INSERT INTO {pg_table} (name, source, category, info_hash, size, seeders, leechers, imdb, processed, createdAt, updatedAt)
    #         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)""",
    #     title,
    #     "EZTV",
    #     "tv",
    #     info_hash,
    #     f"{size}",
    #     seeders,
    #     leechers,
    #     None,
    #     False,
    #     created_at,
    #     updated_at,
    # )

    except KeyError as e:
        logger.exception(e)
    finally:
        await conn.close()


async def consumer(show_queue, ingested_torrents_table, eztv_ingested_pages_table):
    while True:  # Can't use while not queue.empty() as it starts empty and the consumers die before any data is provided by the producer
        show = await show_queue.get()
        if show is None:
            show_queue.task_done()  # Needed to kill all the consumers
            await show_queue.put(None)  # Needed to kill all the consumers
            break  # End the infinite loop for THIS consumer

        # await add_show_to_postgres(
        #     show, ingested_torrents_table, eztv_ingested_pages_table
        # )

        show_queue.task_done()


async def main(showlist_file: str, get_new_showlist: bool) -> None:
    if config.debug_mode:
        ingested_torrents_table = "public.ingested_torrents_debug"
        eztv_ingested_pages_table = "public.eztv_ingested_pages_debug"
    else:
        ingested_torrents_table = "public.ingested_torrents"
        eztv_ingested_pages_table = "public.eztv_ingested_pages"

    await create_postgres_tables(ingested_torrents_table, eztv_ingested_pages_table)

    showlist_with_full_data = await get_eztv_showlist(showlist_file, get_new_showlist)

    show_queue = asyncio.Queue()

    if config.debug_mode:
        logger.debug(
            f"Debug mode enabled, limiting showlist_with_full_data to {config.debug_processing_limit}"
        )
        # keys = list(showlist_with_full_data.keys())[0 : config.debug_processing_limit]
        # showlist_with_full_data = {k: showlist_with_full_data[k] for k in keys}
        showlist_with_full_data[0 : config.debug_processing_limit]

    scraping_task = asyncio.create_task(
        get_showlist_api_data(show_queue, showlist_with_full_data)
    )

    consuming_task = asyncio.create_task(
        consumer(show_queue, ingested_torrents_table, eztv_ingested_pages_table)
    )

    await asyncio.gather(scraping_task, consuming_task)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scrape EZTV and add it to Knight Crawler to be processed"
    )
    parser.add_argument(
        "--showlist-file",
        "-f",
        default="showlist.json",
        help="Specify the file for the showlist. Defaults to 'showlist.json' in the current directory.",
    )
    parser.add_argument(
        "--get-new-showlist",
        "-g",
        action="store_true",
        help="Run additional code with full mode",
    )

    args = parser.parse_args()
    asyncio.run(main(args.showlist_file, args.get_new_showlist))
