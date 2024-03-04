import asyncio
from typing import Any, AsyncGenerator

import aio_pika
from aiormq import AMQPConnectionError
from loguru import logger

from scrapers.config import config
from scrapers.models.media import Media
from scrapers.models.media_collection import MediaCollection


class RabbitInterface:
    """
    Example:
    ```
        example_uri = "amqp://guest:guest@localhost:5672/?heartbeat=30"

        async with await RabbitInterface.create(
                rabbit_uri=example_uri
            ) as rabbit_interface:
                # Publish a dictionary message
                await rabbit_interface.publish({"key": "value"})
    ```
    """

    def __init__(
        self, connection: aio_pika.abc.AbstractRobustConnection, queue_name: str
    ):
        self._connection = connection
        self._queue_name = queue_name

    @classmethod
    async def create(
        cls,
        queue_name: str = "py_scrapers_ingested",
        rabbit_uri: str = config.rabbit_uri,
    ) -> "RabbitInterface":
        try:
            connection: aio_pika.abc.AbstractRobustConnection = (
                await aio_pika.connect_robust(rabbit_uri, loop=asyncio.get_event_loop())  # type: ignore
            )
            logger.info("Successfully connected to RabbitMQ")
        except AMQPConnectionError as exception:
            logger.exception(exception)
            logger.error("There was an error connecting to RabbitMQ")
            exit(1)
        return cls(connection, queue_name)

    async def __aenter__(self):
        self._channel = await self._connection.channel()
        self._queue = await self._channel.declare_queue(self._queue_name)  # type: ignore
        return self

    async def __aexit__(self, exc_type, exc, tb):  # type: ignore
        await self._connection.close()

    async def publish_collection(self, collection: MediaCollection) -> None:
        if type(collection) is not MediaCollection:
            raise TypeError("'collection' must be a MediaCollection")
        # This converts `message` to a json string
        collection_as_json: str = collection.model_dump_json()
        # `json_message.encode()` converts a string to bytes
        await self._channel.default_exchange.publish(
            aio_pika.Message(body=collection_as_json.encode()),
            routing_key=self._queue.name,
        )

    async def publish_media(self, media: Media) -> None:
        if type(media) is not Media:
            raise TypeError("'media' must be a Media object")
        # This converts `message` to a json string
        media_as_json: str = media.model_dump_json()
        # `json_message.encode()` converts a string to bytes
        await self._channel.default_exchange.publish(
            aio_pika.Message(body=media_as_json.encode()),
            routing_key=self._queue.name,
        )

    async def _message_generator(self) -> AsyncGenerator[Any, Any]:
        async with self._queue.iterator() as message_iterator:
            async for message in message_iterator:
                # This converts message from bytes back to a string
                async with message.process():
                    yield message.body.decode()

    async def get_collection(self) -> Any:
        # Retrieve the next message from the queue
        async for message in self._message_generator():
            return MediaCollection.model_validate_json(message)

    async def get_media(self) -> Any:
        # Retrieve the next message from the queue
        async for message in self._message_generator():
            return Media.model_validate_json(message)
