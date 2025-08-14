"""
Map Service Module currently used for manually scraping map data
when new maps are released.
"""

import time
from tempfile import NamedTemporaryFile
from typing import Optional
from zipfile import BadZipFile

from botocore.exceptions import ClientError
from httpx import HTTPError
from sqlalchemy.orm import Session

from src.api.constants import ModHubLabels, ModHubMapFilters
from src.api.core.db.models import Map
from src.api.core.exceptions import MapProcessingError
from src.api.core.logger import logger
from src.api.core.repositories import MapRepository
from src.api.core.schema.maps import MapModel
from src.api.core.schema.mods import ModPreviewModel
from src.api.services.aws_service import AwsService
from src.api.services.file_parser_service import FileParserService
from src.api.services.modhub_service import ModHubService
from src.api.utils import parse_version


class MapService:
    """
    Map Service used for getting map information from the ModHub
    and creating map entries in the database.
    """

    def __init__(
            self,
            db: Session,
            mod_hub_service: Optional[ModHubService] = None,
            aws_service: Optional[AwsService] = None,
            file_parser_service: Optional[FileParserService] = None
    ):
        """
        Constructor for the map service.
        :param db: Database Session.
        :param mod_hub_service: (Optional) ModHub Service instance.
        :param aws_service: (Optional) AWS Service instance.
        :param file_parser_service: (Optional) File Parser Service.
        """
        self.map_repository = MapRepository(db)
        self.mod_hub_service = mod_hub_service or ModHubService()
        self.aws_service = aws_service or AwsService()
        self.file_parser_service = file_parser_service or FileParserService()

    def get_maps(self) -> list[Map]:
        """
        Get all maps.
        :return: List of maps.
        """
        return self.map_repository.all()

    def get_map_by_id(self, map_id: int) -> Optional[Map]:
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
        Function to get new maps from the ModHub, download them and store them
        in the Farmhand S3 bucket and save any information in the database.
        """
        new_maps = await self.check_for_new_maps()

        for map_preview in new_maps:
            map_obj: Map = await self.scrape_map_details(map_preview.id)

            await self.download_map(map_obj.id, map_obj.zip_filename)
            self.extract_map_files(map_obj.id, map_obj.zip_filename)

        if not new_maps:
            logger.info("All scraped and downloaded maps up to date.")
        else:
            logger.info(
                "Successfully scraped and downloaded '%d' maps from the ModHub.",
                len(new_maps)
            )

    async def scrape_map_details(self, map_id: int) -> Optional[Map]:
        """
        Scrape a map from the ModHub and save or update its data based on the map's
        version.
        :param map_id: The id of the ModHub map to scrape.
        :return: Map object if its successfully scraped and stored in the database.
        """
        mod_detail = await self.mod_hub_service.scrape_mod(map_id)

        if mod_detail.category == "Prefab":
            logger.warning("Found a prefab within one of the maps categories, ignoring...")
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

    async def _get_mod_hub_maps(self) -> list[ModPreviewModel]:
        """
        Get all map mod_id's from the Farming Simulator ModHub.
        :return: List of mod hub IDs.
        """
        map_preview = []

        # iterate over all the map filters and make requests to each category's mod page.
        for map_filter in ModHubMapFilters:
            pages = await self.mod_hub_service.get_pages(map_filter)

            for page in pages:
                mod_ids = await self.mod_hub_service.scrape_mods(category=map_filter, page=page)
                map_preview.extend(mod_ids)
        return map_preview

    async def check_for_new_maps(self) -> list[ModPreviewModel]:
        """
        Check for any new or updated maps from ModHub and return them.
        """
        new_maps = []
        existing_map_ids: list = [map_obj.id for map_obj in self.get_maps()]

        for mod_preview in await self._get_mod_hub_maps():
            is_new_or_updated = mod_preview.label in [ModHubLabels.NEW, ModHubLabels.UPDATE]
            is_not_prefab = mod_preview.label != ModHubLabels.PREFAB
            not_in_db = mod_preview.id not in existing_map_ids

            if is_new_or_updated:
                map_obj: Optional[Map] = self.map_repository.get_by_id(mod_preview.id)

                if not map_obj:
                    logger.info("New map: '%s' (%d)", mod_preview.name, mod_preview.id)
                    new_maps.append(mod_preview)
                    continue

                mod_detail = await self.mod_hub_service.scrape_mod(mod_preview.id)
                logger.debug(
                    "Checking versions - current: %s | preview: %s",
                    map_obj.version,
                    mod_detail.version
                )

                if self.is_newer_version(map_obj.version, mod_detail.version):
                    logger.info("Found new version of: '%s' (%d)", map_obj.name, map_obj.id)
                    new_maps.append(mod_preview)
                else:
                    logger.info(
                        "Map: '%s' (%d) already up to date: %s",
                        map_obj.name,
                        map_obj.id,
                        map_obj.version
                    )

            elif not_in_db and is_not_prefab:
                logger.info(
                    "Map not labeled as new or update, but missing from maps table: %s",
                    mod_preview.name
                )
                new_maps.append(mod_preview)

        logger.info("Found %d new map(s).", len(new_maps))

        return new_maps

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
                "Failed scraping or downloading map %s from ModHub. Reason: %s",
                map_id,
                exc
            )
            raise

    def extract_map_files(self, map_id: int, filename: str):
        """
        Download and extract the zip file contents from S3 and re-upload
        all required files for XML parsing.
        :param map_id: The id of the map.
        :param filename: The zip filename of the map.
        """
        start_time = time.monotonic()

        object_key = f"{map_id}/{filename}"

        with NamedTemporaryFile(suffix=".zip") as temp_zip:
            logger.info(f"Extracting files from: {object_key}")
            self.aws_service.download_object(key=object_key, download_location=temp_zip.name)

            try:
                extracted = self.file_parser_service.extract_zip(temp_zip.name)
                restructured_files = self.file_parser_service.restructure_files(
                    extracted.files,
                    extracted.root_dir
                )
            except (FileNotFoundError, BadZipFile, PermissionError) as exc:
                logger.error("Failed to extract or restructure files from map file: %s", exc)
                raise MapProcessingError(f"Failed to process map data from '{map_id}': {str(exc)}")

            try:
                logger.info(f"Attempting to upload {len(extracted.files)} files to bucket...")
                output_directory = object_key.rsplit(".", 1)[0]
                s3_uri = self.aws_service.upload_directory_contents(
                    restructured_files, extracted.root_dir, output_directory
                )
                self.map_repository.update(map_id, data_uri=s3_uri)
            finally:
                extracted.temp_dir.cleanup()

        elapsed_time = time.monotonic() - start_time
        logger.debug("Extracted data from %s in %.2f seconds.", object_key, elapsed_time)

    async def extract_files_from_all_maps(self):
        """
        (temp) Extract all files from all the maps stored within the database.
        """
        start_time = time.monotonic()
        maps = self.get_maps()
        logger.info("Starting file extraction process for %d maps.", len(maps))

        for map_obj in maps:
            logger.info("Extracting files from map: '%s' (%d)", map_obj.name, map_obj.id)
            self.extract_map_files(map_obj.id, map_obj.zip_filename)

        elapsed_time = time.monotonic() - start_time
        logger.debug("Extracted data from %d maps in %.2f seconds.", len(maps), elapsed_time)

    @staticmethod
    def is_newer_version(current_version: str, new_version: str) -> bool:
        """
        Compare two version strings like '1.0.0.0'.
        Return True if new_version is greater.
        :param new_version: The new map version from ModHub.
        :param current_version: The current map version in the db
        """
        return parse_version(new_version) > parse_version(current_version)
