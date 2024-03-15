import asyncio
from pathlib import Path

import typer
from loguru import logger
from typing_extensions import Annotated

from scrapers import logging
from scrapers.consumer import start_a_consumer
from scrapers.producer import start_producer

app_typer = typer.Typer(add_completion=False)


def create_data_directory(data_directory_str: str) -> Path:
    data_directory: Path = Path(data_directory_str)

    if not data_directory.exists():
        create = typer.confirm(
            f"Data directory: '{str(data_directory)}' does not exist. Create it?"
        )

        if create:
            try:
                data_directory.mkdir(parents=True)
            except Exception as exception:
                logger.exception(exception)
                logger.error("There was an error creating the data directory.")
                raise typer.Exit(code=1)
        else:
            logger.error("Cannot proceed without a valid data directory.")
            raise typer.Exit(code=1)

    return data_directory


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
    # Directory to store scraped data
    data_directory_str: Annotated[
        str,
        typer.Option("--data-directory", "-d", help="Directory to store scraped data"),
    ] = str(Path.cwd() / "data"),
    # Verbosity level of the logger
    log_level: Annotated[
        str,
        typer.Option("--log-level", "-l", help="Verbosity level of the logger"),
    ] = "DEBUG",
    # Scrape EZTV
    scrape_eztv: Annotated[bool, typer.Option(help="Scrape EZTV")] = True,
):
    """
    Start a producer. Only start one.
    """
    logging.init(log_level, "producer")
    data_directory: Path = create_data_directory(data_directory_str)
    asyncio.run(start_producer(data_directory, scrape_eztv))


if __name__ == "__main__":
    app_typer()
