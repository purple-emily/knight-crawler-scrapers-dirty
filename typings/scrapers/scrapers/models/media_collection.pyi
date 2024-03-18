"""
This type stub file was generated by pyright.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import NoReturn

from pydantic import BaseModel

from scrapers.models.media import Media

"""
This type stub file was generated by pyright.
"""

class MediaCollection(BaseModel):
    collection: dict[str, Media] = ...
    last_updated: datetime | None = ...
    async def add_media(self, media: Media, lock: asyncio.Lock) -> bool: ...
    async def get_media(self, url: str, lock: asyncio.Lock) -> Media: ...
    async def update_media(self, media: Media, lock: asyncio.Lock) -> bool: ...
    async def is_expired(self, lock: asyncio.Lock) -> bool:
        """This function is a simple wrapper to check if the collection is old."""

    async def missing_imdbs(self, lock: asyncio.Lock) -> list[str]: ...
    async def save_to_file(
        self, filename: str, lock: asyncio.Lock, data_directory: Path = ...
    ) -> NoReturn: ...
    @classmethod
    async def load_from_file(
        cls, filename: str, data_directory: Path
    ) -> MediaCollection: ...
