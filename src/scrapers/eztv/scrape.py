import argparse
import asyncio
import datetime
import json
import os
import re
from datetime import timedelta

import aiofiles
import aiohttp
import arrow
import asyncpg
import redis
from aiolimiter import AsyncLimiter
from loguru import logger

from scrapers.util import config

redis_pool = redis.ConnectionPool(
    host=os.getenv("REDIS_HOST"),
    port=os.getenv("REDIS_PORT"),
    db=os.getenv("REDIS_DB"),
    password=os.getenv("REDIS_PASSWORD"),
)


async def create_postgres_table(pg_table: str) -> None:
    logger.debug(f"Creating postgres table `{pg_table}` if it does not exist")
    conn = await asyncpg.connect(
        user=config.postgres_user,
        password=config.postgres_password,
        database=config.postgres_db,
        host=config.postgres_host,
        port=config.postgres_port,
    )
    try:
        await conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {pg_table} (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255),
            source VARCHAR(255),
            category VARCHAR(255),
            info_hash VARCHAR(255),
            size VARCHAR(255),
            seeders INTEGER,
            leechers INTEGER,
            imdb VARCHAR(255),
            processed BOOLEAN,
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

    eztv_showlist_url = f"{config.eztv_url}/showlist"
    logger.info(f"Pulling showlist from `{eztv_showlist_url}`.")

    async with aiohttp.ClientSession() as session:
        async with session.get(eztv_showlist_url) as html_response:
            html_response = await html_response.text()

    shows_regex_pattern = r'"/shows/[^"]+"'

    # Get only the show URLs from the response
    showlist_urls = re.findall(shows_regex_pattern, html_response)

    # Remove speech marks from the url
    # Before:
    #     '"/shows/577224/cybersleuths-the-idaho-murders/"'
    # After:
    #     '/shows/577224/cybersleuths-the-idaho-murders/'
    showlist_urls = [url.strip('"') for url in showlist_urls]
    # Add the eztv url to the beginning of the url
    # Before:
    #     "/shows/577224/cybersleuths-the-idaho-murders/"
    # After:
    #     "https://eztvx.to/shows/577224/cybersleuths-the-idaho-murders/"
    return [f"{config.eztv_url}{url}" for url in showlist_urls]


async def add_imdbid_to_showlist(urls):
    async def add_imdbid_to_show(url: str, rate_limit):
        async with rate_limit:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    html_response = await response.text()

            imdb_regex_pattern = r"https://www.imdb.com/title/tt([0-9]+)/"
            try:
                imdb_id = re.search(imdb_regex_pattern, html_response).group(1)
            except AttributeError:
                imdb_id = None

            return url, imdb_id

    rate_limit = AsyncLimiter(config.rate_limit_per_second, 1)
    logger.info(
        f"Searching for IMDb id's for {len(urls)} shows. This may take up to 10 minutes, please wait."
    )
    showlist_with_imdbid = await asyncio.gather(
        *(add_imdbid_to_show(url, rate_limit) for url in urls)
    )
    return dict(showlist_with_imdbid)


async def write_json(file, showlist_with_imdbid):
    data = {
        "timestamp": arrow.now().isoformat(),
        "showlist_with_imdbid": showlist_with_imdbid,
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
        raw_showlist = await update_raw_showlist()

        if config.debug_mode:
            logger.debug(
                f"Debug mode enabled, limiting raw_showlist to {config.debug_processing_limit}"
            )
            raw_showlist = raw_showlist[0 : config.debug_processing_limit]

        showlist_with_imdbid = await add_imdbid_to_showlist(raw_showlist)

        await write_json(eztv_showlist_file, showlist_with_imdbid)

    # Check if the showlist file exists
    else:
        # The file exists, so we are going to load the data from it
        logger.debug(f"Loading saved showlist `{eztv_showlist_file}`")
        async with aiofiles.open(eztv_showlist_file, "r") as json_file:
            data = json.loads(await json_file.read())
            showlist_with_imdbid = data["showlist_with_imdbid"]

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

            raw_showlist = await update_raw_showlist()
            # new_or_invalid_shows
            # This should check the loaded data `showlist_with_imdbid` and compare it to the new raw_showlist
            # If the url in raw_showlist doesn't exist as a key in `showlist_with_imdbid` we add it to `new_or_invalid_shows`
            # If the url is in `showlist_with_imdbid` but the value is None we add it to `new_or_invalid_shows`
            # json examples:
            # "https://eztvx.to/shows/449713/textmewhenyougethome/": "tt19552690",
            # "https://eztvx.to/shows/482/5-inch-floppy/": null,
            new_or_invalid_shows = []

            for url in raw_showlist:
                if url not in showlist_with_imdbid or showlist_with_imdbid[url] is None:
                    new_or_invalid_shows.append(url)

            logger.info(f"{len(new_or_invalid_shows)} shows require updating.")

            updated_shows = await add_imdbid_to_showlist(new_or_invalid_shows)

            showlist_with_imdbid.update(updated_shows)

            await write_json(eztv_showlist_file, showlist_with_imdbid)

    logger.debug(f"The showlist contains {len(showlist_with_imdbid)} series")
    return showlist_with_imdbid


async def split_dict_into_batches(dictionary, batch_size):
    """
    Split a dictionary into batches, yielding key-value pairs.

    Args:
        dictionary (dict): The dictionary to split into batches.

    Yields:
        dict: A batch of key-value pairs.

    """
    keys = list(dictionary.keys())
    # values = list(dictionary.values())

    num_full_loops = len(keys) // batch_size
    remainder = len(keys) % batch_size

    # Yield full batches
    for i in range(num_full_loops):
        batch_keys = keys[i * batch_size : (i + 1) * batch_size]
        batch_values = [dictionary[key] for key in batch_keys]
        yield dict(zip(batch_keys, batch_values))

    # Yield remainder batch if exists
    if remainder:
        batch_keys = keys[num_full_loops * batch_size :]
        batch_values = [dictionary[key] for key in batch_keys]
        yield dict(zip(batch_keys, batch_values))


async def get_showlist_api_data(torrent_queue, showlist):
    async def get_show_api_data(torrent_queue, url, rate_limit):
        async with rate_limit:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    json_response = await response.json()

            await torrent_queue.put(json_response)

    rate_limit = AsyncLimiter(config.rate_limit_per_second, 1)

    urls = [
        f"{config.eztv_url}/api/get-torrents?imdb_id={imdb_id}"
        for _, imdb_id in showlist.items()
        if imdb_id is not None
    ]

    logger.info(
        f"Getting API data for {len(urls)} shows. This may take up to 10 minutes, please wait."
    )
    await asyncio.gather(
        *(get_show_api_data(torrent_queue, url, rate_limit) for url in urls)
    )

    await torrent_queue.put(None)


async def process_api_page(api_page, pg_table):
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
        values = []

        for torrent in api_page["torrents"]:
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
                FROM {pg_table}
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
            values.append(new_torrent)

        # Insert data into the database
        logger.info(
            f"Processing {len(values)} torrents for series `{api_page["imdb_id"]}`"
        )
        await conn.executemany(
            f"""INSERT INTO {pg_table} (name, source, category, info_hash, size, seeders, leechers, imdb, processed, "createdAt", "updatedAt")
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)""",
            values,
        )

    except KeyError:
        pass
    finally:
        await conn.close()


async def consumer(torrent_queue, pg_table):
    while True:
        api_page = await torrent_queue.get()
        if api_page is None:
            torrent_queue.task_done()  # Needed to kill all the consumers
            await torrent_queue.put(None)  # Needed to kill all the consumers
            break  # End the infinite loop for THIS consumer
        await process_api_page(api_page, pg_table)
        torrent_queue.task_done()


async def main(showlist_file: str, get_new_showlist: bool) -> None:
    if config.debug_mode:
        pg_table = "public.ingested_torrents_debug"
    else:
        pg_table = "public.ingested_torrents"

    await create_postgres_table(pg_table)

    showlist_with_imdbid = await get_eztv_showlist(showlist_file, get_new_showlist)
    torrent_queue = asyncio.Queue()

    if config.debug_mode:
        logger.debug(
            f"Debug mode enabled, limiting showlist_with_imdbid to {config.debug_processing_limit}"
        )
        keys = list(showlist_with_imdbid.keys())[0 : config.debug_processing_limit]
        showlist_with_imdbid = {k: showlist_with_imdbid[k] for k in keys}

    scraping_task = asyncio.create_task(
        get_showlist_api_data(torrent_queue, showlist_with_imdbid)
    )

    consuming_task = asyncio.create_task(consumer(torrent_queue, pg_table))

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
