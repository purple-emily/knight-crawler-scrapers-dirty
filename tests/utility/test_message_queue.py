import random
import string

import pytest

from scrapers.models.media import Media
from scrapers.utility.message_queue import RabbitInterface

# docker run -d --hostname my-rabbit --name some-rabbit -p 5672:5672 rabbitmq:3


@pytest.mark.asyncio
@pytest.mark.slow
async def test_publish_media_success(media_examples, rabbit_container):
    test_rabbit_uri = "amqp://guest:guest@localhost:5672/?heartbeat=30"

    show1, show2, show3, *_ = media_examples
    random_string = "".join(random.choices(string.ascii_letters + string.digits, k=10))

    async with await RabbitInterface.create(
        queue_name=random_string, rabbit_uri=test_rabbit_uri
    ) as rabbit_interface:
        # Publish three shows
        await rabbit_interface.publish_media(show1)
        await rabbit_interface.publish_media(show2)
        await rabbit_interface.publish_media(show3)

        # Get the first show
        retrieved_show_1: Media = await rabbit_interface.get_media()
        # Make sure it's the correct one
        assert isinstance(retrieved_show_1, Media)
        assert retrieved_show_1 == show1
        assert retrieved_show_1 != show2
        assert retrieved_show_1 != show3

        # Get the second show
        retrieved_show_2: Media = await rabbit_interface.get_media()
        # Make sure it's the correct one
        assert isinstance(retrieved_show_2, Media)
        assert retrieved_show_2 != show1
        assert retrieved_show_2 == show2
        assert retrieved_show_2 != show3

        # Get the third show
        retrieved_show_3: Media = await rabbit_interface.get_media()
        # Make sure it's the correct one
        assert isinstance(retrieved_show_3, Media)
        assert retrieved_show_3 != show1
        assert retrieved_show_3 != show2
        assert retrieved_show_3 == show3
