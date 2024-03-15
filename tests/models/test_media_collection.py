import asyncio
import json
from pathlib import Path

import aiofiles
import arrow
import pytest

from scrapers.models.media import Media
from scrapers.models.media_collection import MediaCollection


@pytest.mark.asyncio
async def test_add(media_examples):
    show1, *_ = media_examples

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

    assert eztv_collection.collection == new_eztv_collection.collection
    assert eztv_collection.last_updated == new_eztv_collection.last_updated


@pytest.mark.asyncio
async def test_incorrect_load(tmp_path):
    file_name = "eztv"
    file = Path(tmp_path / f"{file_name}.json")

    # Collection 1 tests load conditions if the file does not exist.
    collection1: MediaCollection = await MediaCollection.load_from_file(
        file_name, tmp_path
    )

    assert collection1.collection == {}
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

    assert collection2.collection == {}
    assert (
        collection2.last_updated
        != arrow.get("2024-03-12 09:58:41.306122+00:00").datetime
    )


@pytest.mark.asyncio
async def test_update_media(media_examples):
    show1, show2, show3, *_ = media_examples

    collection_lock = asyncio.Lock()
    eztv_collection: MediaCollection = MediaCollection()
    await asyncio.gather(
        *(
            eztv_collection.add_media(show, collection_lock)
            for show in [show1, show2, show3]
        )
    )

    show1_with_edits = show1.model_copy()
    show1_with_edits.status = "Ongoing"

    assert await eztv_collection.update_media(show1_with_edits, collection_lock)

    updated_show: Media = await eztv_collection.get_media(
        show1_with_edits.url, collection_lock
    )

    assert updated_show != show1
    assert updated_show.title == show1.title
    assert updated_show.type == show1.type
    assert updated_show.imdb == show1.imdb
    assert updated_show.status != show1.status
    assert updated_show.last_updated != show1.last_updated

    assert not await eztv_collection.update_media(show1_with_edits, collection_lock)


@pytest.mark.asyncio
async def test_missing_imdbs(media_examples):
    show1, show2, show3, *_ = media_examples

    collection_lock = asyncio.Lock()
    eztv_collection: MediaCollection = MediaCollection()
    await asyncio.gather(
        *(
            eztv_collection.add_media(show, collection_lock)
            for show in [show1, show2, show3]
        )
    )

    missing_imdb_list = await eztv_collection.missing_imdbs(collection_lock)
    assert len(missing_imdb_list) == 0

    show1_with_no_imdb = show1.model_copy()
    show1_with_no_imdb.imdb = None
    assert await eztv_collection.update_media(show1_with_no_imdb, collection_lock)

    show2_with_no_imdb = show2.model_copy()
    show2_with_no_imdb.imdb = None
    assert await eztv_collection.update_media(show2_with_no_imdb, collection_lock)

    missing_imdb_list_2 = await eztv_collection.missing_imdbs(collection_lock)
    assert len(missing_imdb_list_2) == 2
