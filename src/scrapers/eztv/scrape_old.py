# async def fetch_imdb_id(url):
#     page = await fetch_data(url, "text")
#     tree = html.fromstring(page)
#     imdb_link = tree.xpath(
#         "/html/body/div/div[5]/table/tbody/tr[2]/td/center/table[2]/tbody/tr[2]/td[1]/a[1]/@href"
#     )
#     if imdb_link:
#         return imdb_link[0].split("/")[-2]  # Extracting IMDB id from the URL
#     return None


# async def scrape_and_queue_data(queue, debug_mode=False):
#     url = "https://eztvx.to/showlist/"
#     page = await fetch_data(url, "text")
#     tree = html.fromstring(page)
#     links = tree.xpath("/html/body/div/table[2]/tbody/tr[4]/td[1]/a/@href")
#     for link in links[5]:
#         if "/shows/" in link:
#             imdb_id = await fetch_imdb_id(f"https://eztvx.to{link}")
#             if imdb_id:
#                 await queue.put(imdb_id)
#             await asyncio.sleep(15)
#     # page = 1
#     # while True:
#     #     # Only scrape data from page 1 in debug mode
#     #     if debug_mode and page > 3:
#     #         break
#     #     if page > 100:
#     #         break
#     #     url = f"https://eztvx.to/api/get-torrents?limit=100&page={page}"
#     #     data = await fetch_data(url)
#     #     logger.debug(f"Fetched data from page {page}")
#     #     await queue.put(data)
#     #     page += 1


# async def process_torrents(imdb_id, debug_mode, pg_table, redis_client):
#     url = f"https://eztvx.to/api/get-torrents?imdb_id={imdb_id}"
#     data = await fetch_data(url, "json")
#     if not data.get("error"):
#         await store_data_in_database(data, debug_mode, pg_table, redis_client)


# async def store_data_in_database(data, debug_mode, pg_table, redis_client):
#     if debug_mode:
#         redis_expire_time_seconds = 15
#     else:
#         redis_expire_time_seconds = 3600

#     conn = await asyncpg.connect(
#         user=os.getenv("POSTGRES_USER"),
#         password=os.getenv("POSTGRES_PASSWORD"),
#         database=os.getenv("POSTGRES_DB"),
#         host=os.getenv("POSTGRES_HOST"),
#     )

#     for torrent in data["torrents"]:
#         title = torrent["title"]
#         info_hash = torrent["hash"]
#         size = int(torrent["size_bytes"])
#         seeders = torrent["seeds"]
#         leechers = torrent["peers"]
#         created_at = datetime.datetime.now()
#         updated_at = created_at

#         if debug_mode:
#             redis_key = f"py_eztv_scraper_{info_hash}_debug"
#         else:
#             redis_key = f"py_eztv_scraper_{info_hash}"

#         if redis_client.exists(redis_key):
#             logger.debug(f"Skipping (redis) torrent {title} with infoHash {info_hash}")
#             continue  # Skip processing if already cached in Redis

#         exists_query = f"""
#         SELECT EXISTS (
#             SELECT 1
#             FROM public.{pg_table}
#             WHERE info_hash = $1 AND source = $2
#         );
#         """
#         exists = await conn.fetchval(exists_query, info_hash, "EZTV")

#         if exists:
#             logger.debug(
#                 f"Skipping (postgres) torrent {title} with infoHash {info_hash}"
#             )
#             redis_client.set(f"{redis_key}", "cached", ex=redis_expire_time_seconds)
#             continue  # Skip processing if already in Postgres

#         logger.debug(f"Processing torrent {title} with infoHash {info_hash}")

#         # Insert data into the database
#         await conn.execute(
#             #
#             f"""INSERT INTO public.{pg_table} (name, source, category, info_hash, size, seeders, leechers, imdb, processed, "createdAt", "updatedAt")
#                 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)""",
#             title,
#             "EZTV-py",
#             "tv",
#             info_hash,
#             f"{size}",
#             seeders,
#             leechers,
#             None,
#             False,
#             created_at,
#             updated_at,
#         )

#         redis_client.set(f"{redis_key}", "cached", ex=redis_expire_time_seconds)

#     await conn.close()


# async def process_data(queue, debug_mode, pg_table, redis_client):
#     while not queue.empty():
#         imdb_id = await queue.get()
#         # Process the data
#         # added_torrents_count = await process_torrents(imdb_id, debug_mode, pg_table, redis_client)
#         await process_torrents(imdb_id, debug_mode, pg_table, redis_client)
#         queue.task_done()


# async def fetch_data(url: str, return_type: str) -> None:
#     async with aiohttp.ClientSession() as session:
#         async with session.get(url) as response:
#             if return_type == "json":
#                 return await response.json()
#             elif return_type == "text":
#                 return await response.text()
