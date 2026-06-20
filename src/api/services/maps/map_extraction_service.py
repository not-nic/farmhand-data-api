import time
from tempfile import NamedTemporaryFile
from zipfile import BadZipFile

from sqlalchemy.orm import Session

from src.api.core.db.models import Map
from src.api.core.exceptions import MapProcessingError
from src.api.core.logger import logger
from src.api.services.aws_service import AwsService
from src.api.services.file_parser_service import FileParserService
from src.api.services.maps.map_service import MapService


class MapExtractionService:
    def __init__(
            self,
            db: Session,
            map_service: MapService | None = None,
            aws_service: AwsService | None = None,
            file_parser_service: FileParserService | None = None,
    ):
        self.map_service = map_service or MapService(db)
        self.aws_service = aws_service or AwsService()
        self.file_parser_service = file_parser_service or FileParserService()

    def extract_map_files(self, map: Map):
        """
        Download and extract the zip file contents from S3 and re-upload
        all required files for XML parsing.
        :param map: The map object.
        """
        start_time = time.monotonic()

        object_key = f"{map.id}/{map.zip_filename}"

        with NamedTemporaryFile(suffix=".zip") as temp_zip:
            logger.info(f"Extracting files from: {object_key}")
            self.aws_service.download_object(key=object_key, download_location=temp_zip.name)

            try:
                extracted = self.file_parser_service.extract_zip(temp_zip.name)
                restructured_files = self.file_parser_service.restructure_files(
                    extracted.files, extracted.root_dir
                )
            except (FileNotFoundError, BadZipFile, PermissionError) as exc:
                logger.error("Failed to extract or restructure files from map file: %s", exc)
                raise MapProcessingError(f"Failed to process map data from '{map.id}': {str(exc)}")

            try:
                logger.info(f"Attempting to upload {len(extracted.files)} files to bucket...")
                output_directory = object_key.rsplit(".", 1)[0]
                s3_uri = self.aws_service.upload_directory_contents(
                    restructured_files, extracted.root_dir, output_directory
                )
                self.map_service.update_map(map, data_uri=s3_uri)
            finally:
                extracted.temp_dir.cleanup()

        elapsed_time = time.monotonic() - start_time
        logger.debug("Extracted data from %s in %.2f seconds.", object_key, elapsed_time)

    async def extract_files_from_all_maps(self):
        """
        (temp) Extract all files from all the maps stored within the database.
        """
        start_time = time.monotonic()
        maps = self.map_service.get_maps()
        logger.info("Starting file extraction process for %d maps.", len(maps))

        for map_obj in maps:
            logger.info("Extracting files from map: '%s' (%d)", map_obj.name, map_obj.id)
            self.extract_map_files(map_obj)

        elapsed_time = time.monotonic() - start_time
        logger.debug("Extracted data from %d maps in %.2f seconds.", len(maps), elapsed_time)
