import arrow
import docker
import pytest

from scrapers.models.media import Media


def pytest_addoption(parser):
    parser.addoption(
        "--runslow", action="store_true", default=False, help="run slow tests"
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: mark test as slow to run")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        # --runslow given in cli: do not skip slow tests
        return
    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)


@pytest.fixture()
def media_examples():
    return [
        Media(
            url="https://eztvx.to/shows/2583/breaking-bad/",
            title="Breaking Bad",
            type="tv",
            imdb="tt0903747",
            status="Ended",
            last_updated=arrow.get("2024-03-12 09:58:41.306122+00:00").datetime,
        ),
        Media(
            url="https://eztvx.to/shows/481/game-of-thrones/",
            title="Game of Thrones",
            type="tv",
            imdb="tt0944947",
            status="Ended",
            last_updated=arrow.get("2024-03-12 09:58:41.306122+00:00").datetime,
        ),
        Media(
            url="https://eztvx.to/shows/1861/stranger-things/",
            title="Stranger Things",
            type="tv",
            imdb="tt4574334",
            status="Ongoing",
            last_updated=arrow.get("2024-03-12 09:58:41.306122+00:00").datetime,
        ),
    ]


@pytest.fixture(scope="session")
def rabbit_container():
    client: docker.DockerClient = docker.from_env()
    container: docker.models.containers.Container = client.containers.run(
        "rabbitmq:3",
        detach=True,
        ports={"5672": 5672},
        remove=True,
    )
    for line in container.logs(stream=True):
        if "Time to start RabbitMQ:" in str(line.strip()):
            break

    yield container

    container.stop()
