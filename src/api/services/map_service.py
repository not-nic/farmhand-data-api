"""
Map Service Module currently used for manually scraping map data
when new maps are released.
"""
import asyncio
from dataclasses import dataclass, field

from botocore.exceptions import ClientError
from httpx import HTTPError
from sqlalchemy.orm import Session

from src.api.constants import ModHubLabels, ModHubMapFilters
from src.api.core.config import settings
from src.api.core.db.models import Map
from src.api.core.logger import logger
from src.api.core.repositories import MapRepository
from src.api.core.schema.maps import MapModel
from src.api.core.schema.mods import ModDetailModel, ModPreviewModel
from src.api.services.aws_service import AwsService
from src.api.services.modhub_service import ModHubService
from src.api.utils import parse_version


@dataclass
class NewMapCandidate:
    """
    Dataclass containing the ModHub preview and any details
    that have already been fetched from the ModHub.
    """
    preview: ModPreviewModel
    prefetched_detail: ModDetailModel | None = field(default=None)


class MapService:
    """
    Map Service used for getting map information from the ModHub
    and creating map entries in the database.
    """
    INVALID_CATEGORIES: tuple[str] = ("Prefab", "Gameplay")
    MAX_CONCURRENCY: int = 10

    def __init__(
        self,
        db: Session,
        mod_hub_service: ModHubService | None = None,
        aws_service: AwsService | None = None,
    ):
        """
        Constructor for the map service.
        :param db: Database Session.
        :param mod_hub_service: (Optional) ModHub Service instance.
        :param aws_service: (Optional) AWS Service instance.
        """
        self.map_repository = MapRepository(db)
        self.mod_hub_service = mod_hub_service or ModHubService()
        self.aws_service = aws_service or AwsService()

    def get_maps(self) -> list[Map]:
        """
        Get all maps.
        :return: List of maps.
        """
        return self.map_repository.all()

    def get_map_by_id(self, map_id: int) -> Map | None:
        """
        Get a map by its ModHub ID.
        :return: (Optional) the map if it exists.
        """
        return self.map_repository.get_by_id(map_id)

    def create_map(self, map_obj: MapModel) -> Map:
        """
        Create a map in the database from its pydantic MapModel.
        :param map_obj: MapModel attributes to create a map.
        :return: The created map object.
        """
        return self.map_repository.create(**map_obj.model_dump())

    async def get_new_maps(self):
        """
        Function to get new maps from the ModHub and store their information in the DB.
        """
        new_map_candidates = await self.check_for_new_maps()

        if not new_map_candidates:
            logger.info("All scraped and downloaded maps up to date.")
            return

        for candidate in new_map_candidates:
            try:
                map_obj: Map = await self.scrape_map_details(
                    candidate.preview.id,
                    prefetched_detail=candidate.prefetched_detail,
                )
            except (ValueError, HTTPError) as e:
                logger.warning(
                    "Skipping map '%s' (%d) - failed to scrape details: %s",
                    candidate.preview.name,
                    candidate.preview.id,
                    e,
                )
                continue

            if map_obj is None:
                continue

            await self._process_map_download(map_obj)

        logger.info(
            "Successfully scraped and downloaded '%d' maps from the ModHub.", len(new_map_candidates)
        )

    async def check_for_new_maps(self) -> list[NewMapCandidate]:
        """
        Check for any new or updated maps from ModHub and return them.
        """
        new_maps = []
        existing_map_ids: set = {map_obj.id for map_obj in self.get_maps()}

        for mod_preview in await self._get_mod_hub_maps():
            is_new_or_updated = mod_preview.label in [ModHubLabels.NEW, ModHubLabels.UPDATE]
            is_not_prefab = mod_preview.label != ModHubLabels.PREFAB
            not_in_db = mod_preview.id not in existing_map_ids

            if is_new_or_updated:
                map_obj: Map | None = self.map_repository.get_by_id(mod_preview.id)

                if not map_obj:
                    logger.info("New map: '%s' (%d)", mod_preview.name, mod_preview.id)
                    new_maps.append(NewMapCandidate(preview=mod_preview))
                    continue

                candidate = await self._check_for_updated_map(mod_preview, map_obj)
                if candidate:
                    new_maps.append(candidate)

            elif not_in_db and is_not_prefab:
                candidate = await self._validate_untracked_map(mod_preview)
                if candidate:
                    new_maps.append(candidate)

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

        mod_map = self.map_repository.get_by_id(map_id)

        if not mod_map:
            logger.info(f"Creating Map {mod_detail.name} ({mod_detail.id})")
            new_map = MapModel(**mod_detail.model_dump(by_alias=False))
            return self.create_map(new_map)
        else:
            if self.is_newer_version(
                current_version=mod_map.version, new_version=mod_detail.version
            ):
                logger.info(
                    f"Updating Map {mod_detail.name} ({mod_detail.id}) "
                    f"from version {mod_map.version} to {mod_detail.version}"
                )
                self.map_repository.update(mod_map.id, version=mod_detail.version)
                mod_map = self.map_repository.get_by_id(mod_map.id)
            else:
                logger.info(
                    f"Map: {mod_detail.name} ({mod_detail.id}) is already up-to-date "
                    f"(version {mod_map.version})."
                )

        return mod_map

    async def download_map(self, map_id: int, filename: str) -> str:
        """
        Downloads a map and uploads it to an S3 bucket.
        :param map_id: The ID of the map from the ModHub.
        :param filename: The desired filename for the uploaded map.
        :return: (str) The S3 URI of the uploaded map.
        """
        try:
            download_url = await self.mod_hub_service.get_download_url(mod_id=map_id)
            map_content = await self.mod_hub_service.download_mod(download_url)
            return self.aws_service.upload_object(map_content, map_id, filename)
        except ClientError:
            raise
        except HTTPError as exc:
            logger.error(
                "Failed scraping or downloading map %s from ModHub. Reason: %s", map_id, exc
            )
            raise

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

        if self.is_newer_version(map_obj.version, mod_detail.version):
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

    async def _process_map_download(self, map_obj: Map) -> None:
        """
        Download and extract a map if downloads are enabled.
        :param map_obj: The map object to download and extract.
        """
        if settings.ENABLE_MAP_DOWNLOADS:
            await self.download_map(map_obj.id, map_obj.zip_filename)
            # self.extract_map_files(map_obj.id, map_obj.zip_filename)
        else:
            logger.info(
                "Map downloads disabled — skipping download and extraction for '%s' (%d).",
                map_obj.name,
                map_obj.id,
            )

    @staticmethod
    def is_newer_version(current_version: str, new_version: str) -> bool:
        """
        Compare two version strings like '1.0.0.0'.
        Return True if new_version is greater.
        :param new_version: The new map version from ModHub.
        :param current_version: The current map version in the db
        """
        return parse_version(new_version) > parse_version(current_version)
