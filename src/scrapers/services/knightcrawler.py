import asyncio
import datetime
import itertools
import json
import os

import aio_pika
import aiofiles
import asyncpg
import httpx
import jsonpickle
from aiolimiter import AsyncLimiter
from loguru import logger

from scrapers.scrapers import eztv
from scrapers.util.config import config
from scrapers.util.show import Show
from scrapers.util.showlist import ShowList


class CompletedUrls:
    def __init__(self):
        self._completed_urls: set[str] = set()
        self._lock = asyncio.Lock()

    async def add(self, url):
        async with self._lock:
            self._completed_urls.add(url)

    async def get(self) -> set[str]:
        return set(self._completed_urls)

    async def load_from_file(self, filename: str = ".kcprocessed"):
        # Fix the path to the showlist file
        # Before:
        #     showlist_file='showlist.json'
        # After:
        #     showlist_file='D:\\Development\\scrapers\\showlist.json'
        if not os.path.isabs(filename):
            filename = os.path.join(os.getcwd(), filename)

        logger.debug(f"Loading Knight Crawler processed list from `{filename}`")
        try:
            async with aiofiles.open(filename, "r", encoding="utf-8") as file:
                data = json.loads(await file.read())
                self._completed_urls = set(data["completed_urls"])
        except json.JSONDecodeError:
            logger.debug(f"Error decoding JSON in `{filename}`")
        except FileNotFoundError:
            logger.debug(f"File does not exist `{filename}`")

        logger.debug(f"Found {len(self._completed_urls)} urls in processed list.")

    async def save_to_file(self, filename: str = ".kcprocessed"):
        # Fix the path to the showlist file
        # Before:
        #     showlist_file='showlist.json'
        # After:
        #     showlist_file='D:\\Development\\scrapers\\showlist.json'
        if not os.path.isabs(filename):
            filename = os.path.join(os.getcwd(), filename)
        data = {
            "completed_urls": list(self._completed_urls),
        }
        logger.debug(f"Saving Knight Crawler processed list to `{filename}`")
        async with aiofiles.open(filename, "w", encoding="utf-8") as file:
            await file.write(json.dumps(data))


async def produce(show: Show, rate_limit, client):
    logger.debug(f"Scraping show: `{show.name}` with IMDb id: `{show.imdbid}`")
    try:
        show_json = await eztv.get_api_data(show, rate_limit, client)
    except json.decoder.JSONDecodeError:
        return
    return (show, show_json)


async def producer(channel, queue, showlist):
    rate_limit = AsyncLimiter(config.rate_limit_per_second, 1)

    total_number_of_batches = len(list(itertools.batched(showlist, config.batch_size)))

    async with httpx.AsyncClient() as client:
        for batch_number, batch_of_shows in enumerate(
            itertools.batched(showlist, config.batch_size), 1
        ):
            scraped_shows_batch = await asyncio.gather(
                *(produce(show, rate_limit, client) for show in batch_of_shows)
            )

            await channel.default_exchange.publish(
                aio_pika.Message(body=jsonpickle.encode(scraped_shows_batch).encode()),
                routing_key=queue.name,
            )

            percentage_done = (batch_number / total_number_of_batches) * 100
            logger.info(f"Progress: {percentage_done:.2f}% / 100%")

    await channel.default_exchange.publish(
        aio_pika.Message(body=jsonpickle.encode(None).encode()),
        routing_key=queue.name,
    )


async def consume(scraped_show: tuple, postgres_pool, completed_urls: CompletedUrls):
    (show, show_json) = scraped_show

    try:
        logger.debug(
            f"Found {len(show_json["torrents"])} torrents for the show `{show.name}`"
        )

        for torrent in show_json["torrents"]:
            title = torrent["title"]
            info_hash = torrent["hash"].upper()
            size = int(torrent["size_bytes"])
            seeders = torrent["seeds"]
            leechers = torrent["peers"]
            created_at = datetime.datetime.now()
            updated_at = created_at

            exists_query = f"""
                SELECT EXISTS (
                    SELECT 1
                    FROM {config.ingested_torrents_table}
                    WHERE info_hash = $1 AND source = $2
                );
                """

            async with postgres_pool.acquire() as con:
                exists = await con.fetchval(
                    exists_query, info_hash, config.torrent_source
                )

            if exists:
                # This torrent is already in the database. Continue.
                continue

            try:
                async with postgres_pool.acquire() as con:
                    await con.execute(
                        f"""INSERT INTO {config.ingested_torrents_table} (name, source, category, info_hash, size, seeders, leechers, imdb, processed, "createdAt", "updatedAt")
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)""",
                        title,
                        config.torrent_source,
                        "tv",
                        info_hash,
                        f"{size}",
                        seeders,
                        leechers,
                        f"tt{show.imdbid}",
                        False,
                        created_at,
                        updated_at,
                    )
            except asyncpg.exceptions.UniqueViolationError:
                continue

    except KeyError:
        logger.debug(f"Found 0 torrents for the show `{show.name}`")
    finally:
        await completed_urls.add(show.url)
        logger.debug(f"`{show.name}` completed.")


async def consumer(channel, queue, postgres_pool, completed_urls):
    async with queue.iterator() as queue_iter:
        # Cancel consuming after __aexit__
        async for message in queue_iter:
            async with message.process():
                batch_of_shows = jsonpickle.decode(message.body)

                if batch_of_shows is None:
                    await channel.default_exchange.publish(
                        aio_pika.Message(body=jsonpickle.encode(None).encode()),
                        routing_key=queue.name,
                    )
                    break  # End the infinite loop for THIS consumer

                await asyncio.gather(
                    *(
                        consume(show, postgres_pool, completed_urls)
                        for show in batch_of_shows
                    )
                )

                await completed_urls.save_to_file()

    # while True:  # Can't use `while not queue.empty()` as it starts empty and the consumers die before any data is provided by the producer
    #     batch_of_shows = await queue.get()

    #     if batch_of_shows is None:
    #         queue.task_done()  # Needed to kill all the consumers
    #         await queue.put(None)  # Needed to kill all the consumers
    #         break  # End the infinite loop for THIS consumer

    #     await asyncio.gather(
    #         *(consume(show, postgres_pool, completed_urls) for show in batch_of_shows)
    #     )

    #     await completed_urls.save_to_file()

    #     queue.task_done()


async def scrape_eztv(showlist: ShowList, loop: asyncio.AbstractEventLoop):
    completed_urls: CompletedUrls = CompletedUrls()
    await completed_urls.load_from_file()

    # List of shows that have not been completed
    shows_with_imdbid = [
        show
        for show in showlist.get_shows_with_imdbid()
        if show.url not in await completed_urls.get()
    ]

    if config.debug_mode:
        logger.debug(
            f"Debug mode enabled. Limiting to {config.debug_processing_limit} updates"
        )
        shows_with_imdbid = shows_with_imdbid[0 : config.debug_processing_limit]

    logger.info(
        f"{len(shows_with_imdbid)} shows have not been scraped. Starting the scraper, this may take a while..."
    )

    mq_connection: aio_pika.RobustConnection = await aio_pika.connect_robust(
        config.rabbit_uri, loop=loop
    )

    async with mq_connection:
        channel = await mq_connection.channel()
        queue = await channel.declare_queue("eztvpy")
        await producer(channel, queue, shows_with_imdbid)


async def consume_eztv(showlist: ShowList, loop: asyncio.AbstractEventLoop):
    completed_urls: CompletedUrls = CompletedUrls()
    await completed_urls.load_from_file()

    mq_connection: aio_pika.RobustConnection = await aio_pika.connect_robust(
        config.rabbit_uri, loop=loop
    )

    async with mq_connection:
        async with asyncpg.create_pool(
            user=config.postgres_user,
            password=config.postgres_password,
            database=config.postgres_db,
            host=config.postgres_host,
            port=config.postgres_port,
            command_timeout=60,
        ) as postgres_pool:
            channel = await mq_connection.channel()
            queue = await channel.declare_queue("eztvpy")
            logger.info("Consumer is running...")
            await consumer(channel, queue, postgres_pool, completed_urls)
