import asyncio
from datetime import datetime
from pathlib import Path

import aiofiles
import pydantic
from pydantic import BaseModel

from scrapers.models.media import Media


class MediaCollection(BaseModel):
    media_collection: list[Media] = []
    all_urls: set[str] = set()
    last_updated: datetime | None = None

    async def add_media(self, media: Media, lock: asyncio.Lock):
        if media.url not in self.all_urls:
            async with lock:
                self.media_collection.append(media)
                self.all_urls.add(media.url)
                return True

        return False

    async def save_to_file(
        self,
        filename: str,
        lock: asyncio.Lock,
        data_directory: Path = Path.cwd() / "data",
    ):
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
