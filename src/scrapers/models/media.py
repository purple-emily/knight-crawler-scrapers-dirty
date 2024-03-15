from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator


class Media(BaseModel):
    url: str
    title: str
    type: str
    imdb: str | None = None
    status: str
    last_updated: datetime | None = None
    info_hash: str | None = None
    size: str | None = None
    seeders: int | None = None
    leechers: int | None = None

    @field_validator("type")
    @classmethod
    def type_is_movie_or_tv(cls: Any, v: Any):
        if v not in ("anime", "movies", "tv"):
            raise ValueError("type must be 'anime', 'movies' or 'tv'")
        return v

    @field_validator("imdb", mode="before")
    @classmethod
    def fix_imdb_id(cls: Any, v: Any):
        if v is None:
            return None
        if isinstance(v, int):
            return f"tt{v:07d}"
        if isinstance(v, str):
            if v.startswith("tt"):
                return v
            return f"tt{int(v):07d}"
        return v
