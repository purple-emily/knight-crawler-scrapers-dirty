import arrow
import pytest
from pydantic import ValidationError

from scrapers.models.media import Media


def test_good_data():
    media = Media(
        url="/shows/575979/10-things-to-know-about/",
        title="10 Things to Know About",
        type="tv",
        status="Airing: Monday",
        imdb="tt12680866",
        last_updated=arrow.get("2024-03-12 09:58:41.306122+00:00").datetime,
    )

    assert media.url == "/shows/575979/10-things-to-know-about/"
    assert media.title == "10 Things to Know About"
    assert media.type == "tv"
    assert media.status == "Airing: Monday"
    assert media.imdb == "tt12680866"
    assert media.last_updated == arrow.get("2024-03-12 09:58:41.306122+00:00").datetime


def test_imdb_tt_added():
    media = Media(
        url="/shows/575979/10-things-to-know-about/",
        title="10 Things to Know About",
        type="movies",
        status="Airing: Monday",
        imdb="12680866",
        last_updated=arrow.get("2024-03-12 09:58:41.306122+00:00").datetime,
    )

    assert media.imdb == "tt12680866"


def test_imdb_int_to_str():
    media = Media(
        url="/shows/575979/10-things-to-know-about/",
        title="10 Things to Know About",
        type="tv",
        status="Airing: Monday",
        imdb=12680866,  # type: ignore
        last_updated=arrow.get("2024-03-12 09:58:41.306122+00:00").datetime,
    )

    assert media.imdb == "tt12680866"


def test_imdb_is_none():
    media = Media(
        url="/shows/575979/10-things-to-know-about/",
        title="10 Things to Know About",
        type="tv",
        status="Airing: Monday",
        imdb=None,
        last_updated=arrow.get("2024-03-12 09:58:41.306122+00:00").datetime,
    )

    assert media.imdb is None


def test_imdb_float_error():
    with pytest.raises(ValidationError):
        Media(
            url="/shows/575979/10-things-to-know-about/",
            title="10 Things to Know About",
            type="tv",
            status="Airing: Monday",
            imdb=1.0,  # type: ignore
            last_updated=arrow.get("2024-03-12 09:58:41.306122+00:00").datetime,
        )


def test_type_must_be_movies_or_tv():
    with pytest.raises(ValidationError) as exc_info:
        Media(
            url="/shows/575979/10-things-to-know-about/",
            title="10 Things to Know About",
            type="series",
            status="Airing: Monday",
            imdb="tt12680866",
            last_updated=arrow.get("2024-03-12 09:58:41.306122+00:00").datetime,
        )

    assert "type must be 'anime', 'movies' or 'tv'" in str(exc_info.value)
