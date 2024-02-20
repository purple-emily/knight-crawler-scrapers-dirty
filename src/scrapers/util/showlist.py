import asyncio
import json
import os

import aiofiles
import arrow
from loguru import logger

from scrapers.util.show import Show


class ShowList:
    """
    A list of Show objects providing useful helper functions.

    Example usage:
        showlist: ShowList = ShowList()

        # Mock-up of a list of TV shows
        shows = [
            Show(
                "Breaking Bad",
                "Ended",
                "https://www.imdb.com/title/tt0903747/",
                "tt0903747",
            ),
            Show(
                "Game of Thrones",
                "Ended",
                "https://www.imdb.com/title/tt0944947/",
                "tt0944947",
            ),
            Show(
                "Stranger Things",
                "Ongoing",
                "https://www.imdb.com/title/tt4574334/",
                "tt4574334",
            ),
            Show(
                "The Crown",
                "Ongoing",
                "https://www.imdb.com/title/tt4786824/",
                "tt4786824"
            ),
            Show(
                "Friends",
                "Ended",
                "https://www.imdb.com/title/tt0108778/",
                "tt0108778"
            ),
        ]

        await asyncio.gather(*((showlist.add_show(show)) for show in shows))
    """

    def __init__(self):
        self._shows: list[Show] = []
        self._show_urls: set[str] = set()
        self.timestamp: arrow.Arrow = arrow.utcnow()
        self._lock = asyncio.Lock()  # Create a lock for synchronization

    async def add_show(self, show: Show):
        async with self._lock:
            if show.url not in self._show_urls:
                self._shows.append(show)
                self._show_urls.add(show.url)
            else:
                logger.debug(f"Skipping duplicate show {show=}")

    async def get_shows(self) -> list[Show]:
        async with self._lock:
            return self._shows[:]

    def get_shows_with_no_imdbid(self) -> list[Show]:
        return [show for show in self._shows if show.imdbid is None]

    def search_by_url(self, url: str) -> list[Show]:
        return [show for show in self._shows if show.url == url]

    def search_by_name(self, name: str) -> list[Show]:
        return [show for show in self._shows if show.name.lower() == name.lower()]

    def search_by_status(self, status: str) -> list[Show]:
        return [show for show in self._shows if show.status.lower() == status.lower()]

    def search_by_imdbid(self, imdbid: str) -> list[Show]:
        return [show for show in self._shows if show.imdbid == imdbid]

    def show_exists(self, show: Show) -> bool:
        return show in self._shows

    async def load_from_file(self, filename: str = "showlist.json") -> None:
        # Fix the path to the showlist file
        # Before:
        #     showlist_file='showlist.json'
        # After:
        #     showlist_file='D:\\Development\\scrapers\\showlist.json'
        if not os.path.isabs(filename):
            filename = os.path.join(os.getcwd(), filename)

        try:
            async with aiofiles.open(filename, "r", encoding="utf-8") as file:
                data = json.loads(await file.read())
                self._shows = [Show(**show_data) for show_data in data["shows"]]
                # self.timestamp = data["timestamp"]
        except json.JSONDecodeError as e:
            logger.exception(e)
            logger.error("Error decoding JSON. No show list loaded.")

    async def save_to_file(self, filename: str = "showlist.json"):
        # Fix the path to the showlist file
        # Before:
        #     showlist_file='showlist.json'
        # After:
        #     showlist_file='D:\\Development\\scrapers\\showlist.json'
        if not os.path.isabs(filename):
            filename = os.path.join(os.getcwd(), filename)

        data = {
            "shows": [show.__dict__ for show in self._shows],
            "timestamp": self.timestamp.for_json(),
        }
        async with aiofiles.open(filename, "w", encoding="utf-8") as file:
            await file.write(json.dumps(data))

    def __iter__(self):
        return iter(self._shows)

    def __len__(self):
        return len(self._shows)
