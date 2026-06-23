"""
Python module containing the map scraping service for communicating with the
ModHub.
"""
import asyncio
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from src.api.constants import ModHubLabels, ModHubMapFilters, IngestionStatus
from src.api.core.db.models import Map
from src.api.core.logger import logger
from src.api.core.schema.maps import MapModel
from src.api.core.schema.mods import ModDetailModel, ModPreviewModel
from src.api.services.maps.map_service import MapService
from src.api.services.modhub_service import ModHubService
from src.api.utils import is_newer_version


@dataclass
class NewMapCandidate:
    """
    Dataclass containing the ModHub preview and any details
    that have already been fetched from the ModHub.
    """
    preview: ModPreviewModel
    prefetched_detail: ModDetailModel | None = field(default=None)


class MapScrapingService:
    """
    Python class to scrape the ModHub for new and old maps.
    """
    INVALID_CATEGORIES: tuple[str] = ("Prefab", "Gameplay")
    MAX_CONCURRENCY: int = 10

    def __init__(
            self,
            db: Session,
            mod_hub_service: ModHubService | None = None,
            map_service: MapService | None = None
    ):
        self.mod_hub_service = mod_hub_service or ModHubService()
        self.map_service = map_service or MapService(db)

    async def check_for_new_maps(self) -> list[NewMapCandidate]:
        """
        Check for any new or updated maps from ModHub and return them.
        """
        new_maps = []
        existing_map_ids: set = {map_obj.id for map_obj in self.map_service.get_maps()}
        seen_ids: set = set()

        for mod_preview in await self._get_mod_hub_maps():
            if mod_preview.id in seen_ids:
                continue

            is_new_or_updated = mod_preview.label in [ModHubLabels.NEW, ModHubLabels.UPDATE]
            is_not_prefab = mod_preview.label != ModHubLabels.PREFAB
            not_in_db = mod_preview.id not in existing_map_ids

            if is_new_or_updated:
                map_obj: Map | None = self.map_service.get_map_by_id(mod_preview.id)

                if not map_obj:
                    logger.info("New map: '%s' (%d)", mod_preview.name, mod_preview.id)
                    new_maps.append(NewMapCandidate(preview=mod_preview))
                    seen_ids.add(mod_preview.id)
                    continue

                candidate = await self._check_for_updated_map(mod_preview, map_obj)
                if candidate:
                    new_maps.append(candidate)
                    seen_ids.add(mod_preview.id)

            elif not_in_db and is_not_prefab:
                candidate = await self._validate_untracked_map(mod_preview)
                if candidate:
                    new_maps.append(candidate)
                    seen_ids.add(mod_preview.id)

        logger.info("Found %d new map(s).", len(new_maps))
        return new_maps

    async def scrape_map_details(
            self,
            map_id: int,
            prefetched_detail: ModDetailModel | None = None
    ) -> Map | None:
        """
        Scrape a map
        Scrape a map from the ModHub and save or update its data based on the map's
        version. Accepts an optional prefetched detail to avoid a redundant scrape.
        :param map_id: The id of the ModHub map to scrape.
        :param prefetched_detail: (Optional) Already-fetched mod detail from check_for_new_maps.
        :return: A Map object if successfully scraped and stored in the database.
        """
        mod_detail = prefetched_detail or await self.mod_hub_service.scrape_mod(map_id)

        if mod_detail.category in ("Prefab", "Gameplay"):
            logger.warning(
                "Skipping mod '%s' (%d) - invalid category: '%s'",
                mod_detail.name,
                mod_detail.id,
                mod_detail.category,
            )
            return None

        mod_map = self.map_service.get_map_by_id(map_id)

        if not mod_map:
            logger.info(f"Creating Map {mod_detail.name} ({mod_detail.id})")
            new_map = MapModel(**mod_detail.model_dump(by_alias=False))
            return self.map_service.create_map(new_map)
        else:
            if is_newer_version(
                current_version=mod_map.version, new_version=mod_detail.version
            ):
                logger.info(
                    f"Updating Map {mod_detail.name} ({mod_detail.id}) "
                    f"from version {mod_map.version} to {mod_detail.version}"
                )
                self.map_service.update_map(
                    mod_map,
                    version=mod_detail.version,
                    ingestion_status=IngestionStatus.PENDING,
                    ingestion_error=None,
                )
                mod_map = self.map_service.get_map_by_id(mod_map.id)
            else:
                logger.info(
                    f"Map: {mod_detail.name} ({mod_detail.id}) is already up-to-date "
                    f"(version {mod_map.version})."
                )

        return mod_map

    async def _get_mod_hub_maps(self) -> list[ModPreviewModel]:
        """
        Get all map mod_id's from the Farming Simulator ModHub.
        :return: List of mod hub IDs.
        """
        semaphore = asyncio.Semaphore(value=self.MAX_CONCURRENCY)

        filters = list(ModHubMapFilters)
        pages_per_filter = await asyncio.gather(
            *[self.mod_hub_service.get_pages(map_filter) for map_filter in filters]
        )

        scrape_tasks = [
            self._scrape_mods(semaphore, map_filter, page)
            for map_filter, pages in zip(filters, pages_per_filter, strict=True)
            for page in pages
        ]

        results = await asyncio.gather(*scrape_tasks)

        map_previews = []
        for mod_ids in results:
            map_previews.extend(mod_ids)
        return map_previews

    async def _scrape_mods(
            self,
            semaphore: asyncio.Semaphore,
            map_filter: str,
            page: str
    ) -> list[ModPreviewModel]:
        """
        Scrape mods for a given filter and page, respecting the concurrency semaphore.
        :param semaphore: Semaphore to limit concurrent requests to the ModHub.
        :param map_filter: The map filter category to scrape.
        :param page: The page number to scrape.
        :return: List of mod previews scraped from the page.
        """
        async with semaphore:
            return await self.mod_hub_service.scrape_mods(category=map_filter, page=page)

    async def _check_for_updated_map(
            self,
            mod_preview: ModPreviewModel,
            map_obj: Map
    ) -> NewMapCandidate | None:
        """
        Check if an existing map has a newer version on ModHub.
        :param mod_preview: The mod preview from the ModHub listing.
        :param map_obj: The existing map object from the database.
        :return: NewMapCandidate if a newer version is found, None otherwise.
        """
        mod_detail = await self.mod_hub_service.scrape_mod(mod_preview.id)
        logger.debug(
            "Checking versions - current: %s | preview: %s",
            map_obj.version,
            mod_detail.version,
        )

        if is_newer_version(map_obj.version, mod_detail.version):
            logger.info("Found new version of: '%s' (%d)", map_obj.name, map_obj.id)
            return NewMapCandidate(preview=mod_preview, prefetched_detail=mod_detail)

        logger.info(
            "Map: '%s' (%d) already up to date: %s",
            map_obj.name,
            map_obj.id,
            map_obj.version,
        )
        return None

    async def _validate_untracked_map(
            self,
            mod_preview: ModPreviewModel
    ) -> NewMapCandidate | None:
        """
        Validate a map that is missing from the database but not labelled as new or updated.
        Scrapes the full mod detail to confirm it is a valid map category.
        :param mod_preview: The mod preview from the ModHub listing.
        :return: NewMapCandidate if valid, None if the category is invalid.
        """
        logger.info(
            "Map not labeled as new or update, but missing from maps table: %s",
            mod_preview.name,
        )
        mod_detail = await self.mod_hub_service.scrape_mod(mod_preview.id)

        if mod_detail.category in self.INVALID_CATEGORIES:
            logger.info(
                "Skipping mod '%s' (%d) - invalid category: '%s'",
                mod_preview.name,
                mod_preview.id,
                mod_detail.category,
            )
            return None

        return NewMapCandidate(preview=mod_preview, prefetched_detail=mod_detail)

