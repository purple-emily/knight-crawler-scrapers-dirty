import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import NoReturn

import aiofiles
import pydantic
from arrow import Arrow
from pydantic import BaseModel

from scrapers.config import config
from scrapers.models.media import Media


class MediaCollection(BaseModel):
    # media_collection["https://eztvx.to/shows/2583/breaking-bad/"]
    collection: dict[str, Media] = {}
    last_updated: datetime | None = None

    async def add_media(self, media: Media, lock: asyncio.Lock) -> bool:
        async with lock:
            if media.url not in self.collection.keys():
                self.collection[media.url] = media
                return True
        # Media already exists
        return False

    async def get_media(self, url: str, lock: asyncio.Lock) -> Media:
        async with lock:
            if url not in self.collection.keys():
                raise KeyError

            return self.collection[url].model_copy()

    async def update_media(self, media: Media, lock: asyncio.Lock) -> bool:
        # Can't update it if it doesn't exist
        async with lock:
            if media.url not in self.collection.keys():
                raise KeyError

            if self.collection[media.url] != media:
                # Just a total update, no need to waste time
                self.collection[media.url] = media
                self.collection[media.url].last_updated = Arrow.utcnow().datetime
                return True

        # No changes needed
        return False

    async def is_expired(self, lock: asyncio.Lock) -> bool:
        """This function is a simple wrapper to check if the collection is old."""
        async with lock:
            return self.last_updated is None or (
                Arrow.utcnow() - Arrow.fromdatetime(self.last_updated)
            ) > timedelta(hours=config.data_cache_hours)

    async def missing_imdbs(self, lock: asyncio.Lock) -> list[str]:
        async with lock:
            return [
                media.url for media in self.collection.values() if media.imdb is None
            ]

    async def save_to_file(
        self,
        filename: str,
        lock: asyncio.Lock,
        data_directory: Path = Path.cwd() / "data",
    ) -> NoReturn:
        data_directory.mkdir(parents=True, exist_ok=True)
        file: Path = data_directory / f"{filename}.json"

        async with lock:
            collection_as_json: str = self.model_dump_json()

        async with aiofiles.open(file, "w", encoding="utf-8") as open_file:
            await open_file.write(collection_as_json)

    @classmethod
    async def load_from_file(
        cls,
        filename: str,
        data_directory: Path,
    ) -> "MediaCollection":
        file: Path = data_directory / f"{filename}.json"

        try:
            async with aiofiles.open(file, "r", encoding="utf-8") as open_file:
                return cls.model_validate_json(await open_file.read())
        except (FileNotFoundError, pydantic.ValidationError):
            pass

        return cls()
