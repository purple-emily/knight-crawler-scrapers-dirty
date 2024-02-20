import asyncio

import arrow
import httpx
from loguru import logger
from lxml import html  # type: ignore

from scrapers.util import config
from scrapers.util.show import Show
from scrapers.util.showlist import ShowList


async def get_list_of_shows_from_eztv(showlist: ShowList):
    showlist_url = f"{config.eztv_url}{config.eztv_showlist_url}"
    logger.info(f"Pulling showlist from `{showlist_url}`.")

    async with httpx.AsyncClient() as client:
        response = await client.get(showlist_url)
        html_response = response.text

    tree = html.fromstring(html_response)  # type: ignore

    async def html_to_show(html) -> Show:  # type: ignore
        url_element = html.xpath(".//td[@class='forum_thread_post']/a")[0]  # type: ignore
        url = url_element.get("href")  # type: ignore
        show_name = url_element.text_content()  # type: ignore
        status_element = html.xpath(".//td[@class='forum_thread_post']/font")[0]  # type: ignore  # noqa: F821
        status = status_element.text.strip()  # type: ignore

        return Show(url=url, name=show_name, status=status)  # type: ignore

    shows = await asyncio.gather(
        *(html_to_show(show_html) for show_html in tree.xpath('//tr[@name="hover"]'))
    )

    for show in shows:
        await showlist.add_show(show)

    # At this point we have `url`, `show_name` and `status`.
    # Missing the IMDb id


async def main() -> None:
    showlist: ShowList = ShowList()

    # # Mock-up of a list of TV shows
    # shows = [
    #     Show(
    #         "Breaking Bad",
    #         "Ended",
    #         "https://www.imdb.com/title/tt0903747/",
    #         "tt0903747",
    #     ),
    #     Show(
    #         "Game of Thrones",
    #         "Ended",
    #         "https://www.imdb.com/title/tt0944947/",
    #         "tt0944947",
    #     ),
    #     Show(
    #         "Stranger Things",
    #         "Ongoing",
    #         "https://www.imdb.com/title/tt4574334/",
    #         "tt4574334",
    #     ),
    #     Show(
    #         "The Crown", "Ongoing", "https://www.imdb.com/title/tt4786824/", "tt4786824"
    #     ),
    #     Show("Friends", "Ended", "https://www.imdb.com/title/tt0108778/", "tt0108778"),
    # ]

    # await asyncio.gather(*((showlist.add_show(show)) for show in shows))
    try:
        await showlist.load_from_file("showlist_new.json")
    except FileNotFoundError:
        pass

    await showlist.add_show(
        Show(
            url="/shows/472030/100-not-out-100no-503-magdas-big-national-health-check/",
            name="100 Not Out 100NO 503: Magda's Big National Health Check",
            status="Airing:",
        )
    )

    await get_list_of_shows_from_eztv(showlist)

    await showlist.save_to_file()


if __name__ == "__main__":
    asyncio.run(main())
