"""
Map Service Module currently used for manually scraping map data
when new maps are released.
"""
import time
from tempfile import NamedTemporaryFile
from typing import Optional

from sqlalchemy.orm import Session

from src.api.constants import ModHubMapFilters
from src.api.core.db.models import Map
from src.api.core.logger import logger
from src.api.core.repositories import MapRepository
from src.api.core.schema.maps.maps import MapModel
from src.api.services.aws_service import AwsService
from src.api.services.file_parser_service import FileParserService
from src.api.services.modhub_service import ModHubService
from src.api.utils import parse_version


class MapService:
    """
    Map Service used for getting map information from the ModHub
    and creating map entries in the database.
    """

    def __init__(self, db: Session):
        self.mod_hub_service = ModHubService()
        self.map_repository = MapRepository(db)

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

    def create_map(
            self,
            map_obj: MapModel
    ) -> Map:
        """
        Create a map in the database from its pydantic MapModel.
        :param map_obj: MapModel attributes to create a map.
        :return: the created map object.
        """
        return self.map_repository.create(**map_obj.model_dump())

    async def scrape_maps(self):
        """
        Function to get all the maps from the Farming Simulator ModHub
        and store their information into the Maps table of the database.
        :return:
        """
        map_ids = []

        # iterate over all the map filters and make requests to each category's mod page.
        for map_filter in ModHubMapFilters:
            pages = await self.mod_hub_service.get_pages(map_filter)

            for page in pages:
                mod_ids = await self.mod_hub_service.scrape_mods(category=map_filter, page=page)
                map_ids.extend(mod_ids)

        # iterate over all the collected mod ids and scrape the mod page data.
        for mod_id in map_ids:
            mod_detail = await self.mod_hub_service.scrape_mod(mod_id)

            # ignore mod if their category is a Prefab.
            if mod_detail.category == "Prefab":
                logger.info("Found a prefab within one of the maps categories, ignoring...")
                continue

            mod_map = self.map_repository.get_by_id(mod_id)

            if not mod_map:
                logger.info(f"Creating Map {mod_detail.name} ({mod_detail.id})")
                new_map = MapModel(**mod_detail.model_dump(by_alias=False))
                self.create_map(new_map)
            else:
                if self.is_newer_version(
                    current_version=mod_map.version, new_version=mod_detail.version
                ):
                    logger.info(
                        f"Updating Map {mod_detail.name} ({mod_detail.id}) "
                        f"from version {mod_map.version} to {mod_detail.version}"
                    )
                    self.map_repository.update(mod_map.id, version=mod_detail.version)
                else:
                    logger.info(
                        f"Map: {mod_detail.name} ({mod_detail.id}) is already up-to-date "
                        f"(version {mod_map.version})."
                    )

        logger.info("Finished scraping all maps from the ModHub.")

    async def download_maps(self):
        """
        (temp) download all maps from the maps scraped in the database
        will take some time to run based on CDN for each mod.

        TODO:
        - multi-thread this or have it run without async blocking
        - improve it as a background task
        - change the method or create a new one to pull new maps and download them
        - update to download based on version, only download if a version bump.
        """
        aws_service = AwsService()

        for map in self.map_repository.all():
            file_url = await self.mod_hub_service.get_download_url(mod_id=map.id)
            try:
                mod_content = await self.mod_hub_service.download_mod(file_url=file_url)
                aws_service.upload_object(mod_content, map.id, map.zip_filename)
            except Exception as exc:
                logger.error("Error downloading mods: %s ", str(exc))

        logger.info("all maps downloaded and uploaded to S3.")

    async def extract_files(self):
        """
        (temp) extracts the contents from each map that has been
        stored in the bucket using the FileParser.

        TODO:
        - again multi-thread this or have it run without async blocking
        - improve it as a background task
        - change the method or create a new method to pull new maps and extract data from them
        - update to extract based on version, only extract if a version bump.
        """

        start_time = time.monotonic()

        aws_service = AwsService()
        maps = self.get_maps()

        for map_obj in maps:

            object_key = f"{map_obj.id}/{map_obj.zip_filename}"

            with NamedTemporaryFile(suffix=".zip") as temp_zip:
                logger.info(f"object_key: {object_key}")
                aws_service.download_object(key=object_key, download_location=temp_zip.name)

                file_parser_service = FileParserService()
                extracted = file_parser_service.extract_zip(temp_zip.name)
                updated_files = file_parser_service.restructure_files(
                    extracted.files,
                    extracted.root_dir
                )

                try:
                    logger.info(f"Attempting to upload {len(extracted.files)} files to bucket...")
                    output_directory = object_key.rsplit(".", 1)[0]
                    s3_uri = aws_service.upload_directory_contents(
                        updated_files, extracted.root_dir, output_directory
                    )
                    self.map_repository.update(map_obj.id, data_uri=s3_uri)
                finally:
                    extracted.temp_dir.cleanup()

        elapsed_time = time.monotonic() - start_time
        logger.info(f"Extracted data from {len(maps)} maps in {elapsed_time:2f} seconds.")

    @staticmethod
    def is_newer_version(current_version: str, new_version: str) -> bool:
        """
        Compare two version strings like '1.0.0.0'.
        Return True if new_version is greater.
        :param new_version: the new map version from ModHub.
        :param current_version: the current map version in the db
        """
        return parse_version(new_version) > parse_version(current_version)
