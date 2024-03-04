import asyncio
import json
from pathlib import Path

import aiofiles
import arrow
import pytest

from scrapers.models.media import Media
from scrapers.models.media_collection import MediaCollection


@pytest.mark.asyncio
async def test_add():
    show1: Media = Media(
        url="https://eztvx.to/shows/2583/breaking-bad/",
        title="Breaking Bad",
        type="tv",
        imdb="tt0903747",
        status="Ended",
        last_updated=arrow.get("2024-03-12 09:58:41.306122+00:00").datetime,
    )

    collection_lock = asyncio.Lock()
    eztv_collection: MediaCollection = MediaCollection()
    assert await eztv_collection.add_media(show1, collection_lock) is True
    # It should fail on the second attempt, as this show already exists
    assert await eztv_collection.add_media(show1, collection_lock) is False


@pytest.mark.asyncio
async def test_successful_save_and_load(media_examples, tmp_path):
    show1, show2, show3, *_ = media_examples

    collection_lock = asyncio.Lock()
    eztv_collection: MediaCollection = MediaCollection()
    await asyncio.gather(
        *(
            eztv_collection.add_media(show, collection_lock)
            for show in [show1, show2, show3]
        )
    )

    file_name = "eztv"
    await eztv_collection.save_to_file(file_name, collection_lock, tmp_path)
    expected_file = Path(tmp_path / f"{file_name}.json")
    assert expected_file.exists()

    # This tests that the new object contains the same data as the saved object.
    new_eztv_collection: MediaCollection = await MediaCollection.load_from_file(
        file_name, tmp_path
    )

    assert eztv_collection.media_collection == new_eztv_collection.media_collection
    assert eztv_collection.all_urls == new_eztv_collection.all_urls
    assert eztv_collection.last_updated == new_eztv_collection.last_updated


@pytest.mark.asyncio
async def test_incorrect_load(tmp_path):
    file_name = "eztv"
    file = Path(tmp_path / f"{file_name}.json")

    # Collection 1 tests load conditions if the file does not exist.
    collection1: MediaCollection = await MediaCollection.load_from_file(
        file_name, tmp_path
    )

    assert collection1.media_collection == []
    assert collection1.all_urls == set()
    assert (
        collection1.last_updated
        != arrow.get("2024-03-12 09:58:41.306122+00:00").datetime
    )

    json_str: str = json.dumps("Hello")  # type: ignore

    async with aiofiles.open(file, "w", encoding="utf-8") as open_file:
        await open_file.write(json_str)

    assert file.exists()

    # Collection 2 tests load conditions if the file contains bad data.
    collection2: MediaCollection = await MediaCollection.load_from_file(
        file_name, tmp_path
    )

    assert collection2.media_collection == []
    assert collection2.all_urls == set()
    assert (
        collection2.last_updated
        != arrow.get("2024-03-12 09:58:41.306122+00:00").datetime
    )
