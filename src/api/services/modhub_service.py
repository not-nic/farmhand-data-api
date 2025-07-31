"""
Mod Hub Service Module for generic scraping of the Farming Simulator ModHub
pages.
"""
import time
from typing import Optional

import httpx
from bs4 import BeautifulSoup, Tag
from httpx import HTTPError, Response

from src.api.core.config import settings
from src.api.core.logger import logger
from src.api.core.schema.mods import ModModel
from src.api.utils import format_file_size, get_filename_from_url


class ModHubService:
    """
    Module to scrape the Farming Simulator ModHub and get information about Mods.
    """

    async def download_mod(self, file_url: str) -> bytes:
        """
        Downloads a mod from its file_url from the Giants Software CDN.
        :param file_url: the file to download.
        :return: (bytes) of the file response.
        """
        headers = {
            "Referer": settings.BASE_FS_URL,
        }

        start_time = time.monotonic()
        response = await self._make_request(file_url, headers=headers)

        elapsed_time = time.monotonic() - start_time
        file_size = len(response.content)

        logger.info(f"Finished downloading {get_filename_from_url(file_url)} in {elapsed_time:.2f} seconds.")
        logger.info(f"Downloaded file size: {format_file_size(file_size)}")

        return response.content

    async def get_download_url(
            self,
            mod_id: Optional[int] = None,
            page_contents: Optional[BeautifulSoup] = None
    ) -> Optional[str]:
        """
        Gets the download URL either from a mod_id or the page_contents HTML.
        :param mod_id: the id of the mod to download
        :param page_contents: the contents of a 'scraped page'
        :return: mod_url if it exists.
        """

        if page_contents is None and mod_id is None:
            raise ValueError("Either 'mod_id' or 'page_contents' must be provided.")

        if page_contents is None:
            url = self.create_mod_url(mod_id=mod_id)
            response = await self._make_request(url)
            page_contents = BeautifulSoup(response.content, "html.parser")

        download_button = page_contents.find(
            "a",
            class_="button button-buy button-middle button-no-margin expanded"
        )

        return download_button['href'] if download_button else None

    async def scrape_mod(self, mod_id: int) -> ModModel:
        """
        Scrape a mod page and return a pydantic model of the mod details
        :param mod_id: the id of the mod to scrape
        :return: (Mod) Pydantic model or raise value error.
        """
        url = self.create_mod_url(mod_id=mod_id)
        response = await self._make_request(url)

        page_contents = BeautifulSoup(response.content, "html.parser")

        mod_name = page_contents.find("h2", class_="column title-label").get_text(strip=True)
        mod_info = page_contents.find("div", class_="table table-game-info")

        file_url = await self.get_download_url(page_contents=page_contents)

        if mod_info:
            mod_details = self.get_mod_details(mod_info)
            mod_details["id"] = mod_id
            mod_details["name"] = mod_name
            mod_details["file_url"] = file_url
            mod_details["zip_filename"] = get_filename_from_url(file_url)

            logger.info(f"Found mod information for {mod_name} ({mod_id})")

            mod_detail = ModModel(**mod_details)
            return mod_detail
        else:
            logger.warning(
                f"Mod ID: {mod_id} - Unable to scrape mod information "
                f"as 'mod-info div' was not found."
            )
            raise ValueError(
                f"Mod ID: {mod_id} - Unable to scrape mod information "
                f"as 'mod-info div' was not found."
            )

    async def scrape_mods(self, category: Optional[str] = None, page: Optional[str] = None) -> list:
        """
        Scrape the 'mods' pages and get the ids for each mod displayed
        :param category: the category to get mods for i.e. MapFilters constants
        :param page: the page to get mods from.
        :return: a list of mod_ids scraped from the page.
        """
        url = self.create_mods_url(
            category_filter=category if category else "", page=page if category else ""
        )

        response = await self._make_request(url)

        page_contents = BeautifulSoup(response.content, "html.parser")
        rows = page_contents.find_all("div", class_="row")

        mod_ids = []

        # iterate over each row and get the container for each mod
        for row in rows:
            mod_item_containers = row.find_all("div", class_="medium-6 large-3 columns")

            # loop over each container and get the 'mod-item' div and get the id for the
            # mod page from the 'MORE INFO' tag.
            for container in mod_item_containers:
                mod_item = container.find("div", class_="mod-item")
                if mod_item:
                    mod_ids.append(self.get_mod_id(mod_item))

        return mod_ids

    async def get_pages(self, category_filter: Optional[str] = None) -> list:
        """
        Get the amount of 'mod pages' per category, zero indexed for the URL.
        :param category_filter: the category to filter by.
        :return: a list of page numbers from first page to last.
        """
        url = self.create_mods_url(category_filter=category_filter if category_filter else "")

        response = await self._make_request(url)

        page_contents = BeautifulSoup(response.content, "html.parser")
        pagination = self._get_pagination_element(page_contents)

        page_numbers = []

        for li in pagination.find_all("li"):
            # If it's the current page, get the number from the span object.
            if "current" in li.get("class", ""):
                text = li.get_text(strip=True)
                number = "".join([char for char in text if char.isdigit()])
            else:
                a = li.find("a")
                number = a.text.strip() if a and a.text.strip().isdigit() else None

            # Ensure the number is a digit before casting it to int.
            if number and number.isdigit():
                page_numbers.append(int(number))

        if not page_numbers:
            logger.info("No page numbers within the pagination DOM object - returning empty list.")
            return []

        # take one away to zero index the first and last page to match 'pages'.
        first_page = min(page_numbers) - 1
        last_page = max(page_numbers) - 1

        logger.info(
            f"found pages returning all pages between first page: "
            f"'{first_page}' and last page: '{last_page}'"
        )
        return list(range(first_page, last_page + 1))

    @staticmethod
    def create_mods_url(
        category_filter: Optional[str] = None,
        page: Optional[int] = None,
        title: Optional[str] = None,
    ) -> str:
        """
        create a URL to scrape a mod by its category or without.
        :param page: the page to scrape (should be handled as an increment)
        :param category_filter: the category to scrape i.e. FarmsEurope
        :param title: The Farming Sim game version
        :return: a string of the created url
        """
        return (
            f"{settings.BASE_MODS_URL}"
            + (f"?filter={category_filter}" if category_filter else "")
            + (f"&title={title}" if title else "")
            + (f"&page={page}" if page else "")
        )

    @staticmethod
    def create_mod_url(mod_id: int, title: Optional[str] = None) -> str:
        """
        create a ModHub url for a specific mod that can be scraped.
        :param mod_id: the id of the mod to request
        :param title: the Farming Sim game version
        :return: a string of the created url
        """
        return f"{settings.BASE_MOD_URL}?mod_id={mod_id}" + (f"&title={title}" if title else "")

    @staticmethod
    def get_mod_details(mod_info: Tag) -> dict:
        """
        Function to get the stats about a mod author, release date, size, etc
        :param mod_info: HTML Element of the Table
        :return: a dict of key and values e.g. author, mod_size, release date, etc.
        """
        info = {}

        for row in mod_info.find_all("div", class_="table-row"):
            cells = row.find_all("div", class_="table-cell")

            if len(cells) >= 2:
                key = cells[0].get_text(strip=True)
                value = cells[1].get_text(strip=True)
                info[key] = value

        return info

    @staticmethod
    def get_mod_id(mod_item: Tag) -> Optional[int]:
        """
        Get the id for the mod based on the href of the 'MORE_INFO' button.
        :param mod_item: the current mod item
        :return: (int) the id of the mod
        """
        more_info_tag = mod_item.find("a", class_="button-buy")
        if more_info_tag:
            href = more_info_tag.get("href", "")
            if "mod_id=" in href:
                mod_id = href.split("mod_id=")[1].split("&")[0]
                return int(mod_id)

        return None

    @staticmethod
    def _get_pagination_element(page_contents: BeautifulSoup) -> Tag:
        """
        get the pagination element containing page numbers from the ModHub website.
        :param page_contents: the contents of the page
        :return: the pagination page element if it exists.
        """
        # Find the pagination content
        pagination = page_contents.find("ul", class_="pagination")
        if not pagination:
            logger.info(
                "No pagination object found within the DOM - returning empty page number list."
            )
            return []

        return pagination

    @staticmethod
    async def _make_request(url: str, headers: Optional[dict] = None) -> Response:
        """
        Helper method to make requests to Farming simulator's ModHub.
        :param url: the url to request.
        :return: the response data.
        """
        # Investigate silent error when map takes a while to download,
        # likely a timeout from Httpx
        async with httpx.AsyncClient() as client:
            try:
                logger.info(f"Making request to ModHub url: %s", url)
                response = await client.get(url=url, headers=headers if headers else {})
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.error(
                    f"Unable to connect to the ModHub - got status code: {exc.response.status_code}"
                )
                raise HTTPError(message=f"Request failed with status code: {exc.response.status_code}")
        return response
