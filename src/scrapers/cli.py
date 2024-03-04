import asyncio

import typer
from typing_extensions import Annotated

from scrapers import logging
from scrapers.consumer import start_a_consumer
from scrapers.producer import start_producer

app_typer = typer.Typer(add_completion=False)


async def test_command():
    return 1


@app_typer.command()
def consumer(
    log_level: Annotated[
        str, typer.Option(help="Verbosity level of the logger")
    ] = "DEBUG",
):
    """
    Start a consumer. Can run multiple at once.
    """
    logging.init(log_level, "consumer")
    asyncio.run(start_a_consumer())


@app_typer.command()
def producer(
    log_level: Annotated[
        str, typer.Option(help="Verbosity level of the logger")
    ] = "DEBUG",
    scrape_eztv: Annotated[bool, typer.Option(help="Scrape EZTV")] = True,
):
    """
    Start a producer. Only start one.
    """
    logging.init(log_level, "producer")
    asyncio.run(start_producer(scrape_eztv))


if __name__ == "__main__":
    app_typer()
