import asyncio
import datetime
import os

import aiohttp
import asyncpg
import redis
from dotenv import load_dotenv
from loguru import logger

dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path)

redis_pool = redis.ConnectionPool(
    host=os.getenv("REDIS_HOST"),
    port=os.getenv("REDIS_PORT"),
    db=os.getenv("REDIS_DB"),
    password=os.getenv("REDIS_PASSWORD"),
)


async def fetch_data(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()


async def scrape_and_queue_data(queue, debug_mode=False):
    page = 1
    while True:
        # Only scrape data from page 1 in debug mode
        if debug_mode and page > 2:
            break
        if page > 100:
            break
        url = f"https://eztvx.to/api/get-torrents?limit=100&page={page}"
        data = await fetch_data(url)
        logger.debug(f"Fetched data from page {page}")
        await queue.put(data)
        page += 1


async def store_data_in_database(data, debug_mode, pg_table, redis_client):
    if debug_mode:
        redis_expire_time_seconds = 15
    else:
        redis_expire_time_seconds = 3600

    conn = await asyncpg.connect(
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        database=os.getenv("POSTGRES_NAME"),
        host=os.getenv("POSTGRES_HOST"),
    )

    for torrent in data["torrents"]:
        title = torrent["title"]
        info_hash = torrent["hash"]
        size = int(torrent["size_bytes"])
        seeders = torrent["seeds"]
        leechers = torrent["peers"]
        created_at = datetime.datetime.now()
        updated_at = created_at

        if debug_mode:
            redis_key = f"py_eztv_scraper_{info_hash}_debug"
        else:
            redis_key = f"py_eztv_scraper_{info_hash}"

        if redis_client.exists(redis_key):
            logger.debug(f"Skipping (redis) torrent {title} with infoHash {info_hash}")
            continue  # Skip processing if already cached in Redis

        exists_query = f"""
        SELECT EXISTS (
            SELECT 1
            FROM {pg_table}
            WHERE info_hash = $1 AND source = $2
        );
        """
        exists = await conn.fetchval(exists_query, info_hash, "EZTV")

        if exists:
            logger.debug(
                f"Skipping (postgres) torrent {title} with infoHash {info_hash}"
            )
            redis_client.set(f"{redis_key}", "cached", ex=redis_expire_time_seconds)
            continue  # Skip processing if already in Postgres

        logger.debug(f"Processing torrent {title} with infoHash {info_hash}")

        # Insert data into the database
        await conn.execute(
            f"""INSERT INTO {pg_table} (name, source, category, info_hash, size, seeders, leechers, imdb, processed, createdAt, updatedAt)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)""",
            title,
            "EZTV",
            "tv",
            info_hash,
            f"{size}",
            seeders,
            leechers,
            None,
            False,
            created_at,
            updated_at,
        )

        redis_client.set(
            f"py_eztv_scraper_{info_hash}", "cached", ex=redis_expire_time_seconds
        )

    await conn.close()


async def process_data(queue, debug_mode, pg_table, redis_client):
    while not queue.empty():
        data = await queue.get()
        # Process the data
        await store_data_in_database(
            data, debug_mode=debug_mode, pg_table=pg_table, redis_client=redis_client
        )
        queue.task_done()


async def main():
    # Check if debug mode is enabled
    debug_mode = os.getenv("DEBUG_MODE") == "True"

    try:
        conn = await asyncpg.connect(
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            database=os.getenv("POSTGRES_NAME"),
            host=os.getenv("POSTGRES_HOST"),
        )
    except Exception as exception:
        logger.exception(exception)

    if debug_mode:
        pg_table = "ingested_torrents_debug"
    else:
        pg_table = "ingested_torrents"

    await conn.execute(
        f"""CREATE TABLE IF NOT EXISTS public.{pg_table} (
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
            createdAt TIMESTAMP WITH TIME ZONE,
            updatedAt TIMESTAMP WITH TIME ZONE
        );
        """
    )
    await conn.close()

    redis_client = redis.Redis(connection_pool=redis_pool)

    # Start scraping and queuing data
    queue = asyncio.Queue()
    await scrape_and_queue_data(queue, debug_mode=debug_mode)

    tasks = [
        asyncio.create_task(
            process_data(
                queue,
                debug_mode=debug_mode,
                pg_table=pg_table,
                redis_client=redis_client,
            )
        )
        for _ in range(5)
    ]  # Adjust the number of processing tasks as needed
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
    redis_pool.disconnect()
