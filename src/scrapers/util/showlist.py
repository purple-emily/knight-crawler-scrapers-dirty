import asyncio
import json
import os
from typing import Optional

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

    async def add_show(self, show: Show) -> bool:
        async with self._lock:
            if show.url not in self._show_urls:
                self._shows.append(show)
                self._show_urls.add(show.url)
                return True
            else:
                return False

    async def get_shows(self) -> list[Show]:
        async with self._lock:
            return self._shows[:]

    async def update_show_status(self, url: str, status: str):
        """
        Returns:
            bool: true if show updated
        """
        if url not in self._show_urls:
            raise ValueError(f"Show with URL `{url}` not found in the list.")

        for show in self._shows:
            if show.url == url:
                if show.status != status:
                    async with self._lock:
                        show.status = status
                        return True
                return False

    async def update_show_imdbid(self, url: str, imdbid: Optional[str] = None):
        """
        Returns:
            bool: true if show updated
        """
        if imdbid is None:
            # No point updating the IMDb if it's None
            return False

        if url not in self._show_urls:
            raise ValueError(f"Show with URL `{url}` not found in the list.")

        for show in self._shows:
            if show.url == url:
                if show.imdbid != imdbid:
                    async with self._lock:
                        show.imdbid = imdbid
                        return True
                return False

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

    async def load_from_file(self, filename: str = "eztv_showlist.json") -> None:
        # Fix the path to the showlist file
        # Before:
        #     showlist_file='showlist.json'
        # After:
        #     showlist_file='D:\\Development\\scrapers\\showlist.json'
        if not os.path.isabs(filename):
            filename = os.path.join(os.getcwd(), filename)

        logger.debug(f"Attempting to load the showlist from file `{filename}`")
        try:
            async with aiofiles.open(filename, "r", encoding="utf-8") as file:
                data = json.loads(await file.read())
                self._shows = [Show(**show_data) for show_data in data["shows"]]
                self._show_urls = set(data["show_urls"])
                self.timestamp = arrow.get(data["timestamp"])
        except json.JSONDecodeError:
            logger.debug(f"Error decoding JSON in `{filename}`")
        except FileNotFoundError:
            logger.debug(f"File does not exist `{filename}`")

        logger.info(f"Loaded {len(self._shows)} shows from `{filename}`")

    async def save_to_file(self, filename: str = "eztv_showlist.json"):
        # Fix the path to the showlist file
        # Before:
        #     showlist_file='showlist.json'
        # After:
        #     showlist_file='D:\\Development\\scrapers\\showlist.json'
        if not os.path.isabs(filename):
            filename = os.path.join(os.getcwd(), filename)

        data = {
            "shows": [show.__dict__ for show in self._shows],
            "show_urls": list(self._show_urls),
            "timestamp": self.timestamp.for_json(),
        }
        logger.debug(f"Attempting to save the showlist to file `{filename}`")
        async with aiofiles.open(filename, "w", encoding="utf-8") as file:
            await file.write(json.dumps(data))

    def __iter__(self):
        return iter(self._shows)

    def __len__(self):
        return len(self._shows)
