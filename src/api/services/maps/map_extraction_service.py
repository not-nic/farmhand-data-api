"""
A Python module containing a map extraction service to manage the file extraction
from a zip archive that can be parsed within the XML parsing service.
"""

import time
from tempfile import NamedTemporaryFile
from zipfile import BadZipFile

from sqlalchemy.orm import Session

from src.api.constants import IngestionStatus
from src.api.core.db.models import Map
from src.api.core.exceptions import MapProcessingError
from src.api.core.logger import logger
from src.api.services.aws_service import AwsService
from src.api.services.file_parser_service import FileParserService
from src.api.services.maps.map_service import MapService


class MapExtractionService:
    """
    Extracts the required files from a Farming Simulator .zip archive stored
    in S3, restructures them into the farmhand directory format, runs a
    post-processing clean-up pass, and re-uploads the filtered contents.

    Ingestion status transitions are managed by MapIngestionService.
    """

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

    def extract_map_files(self, map_obj: Map) -> None:
        """
        Download the map archive from S3, extract and restructure its contents,
        remove unwanted extras, and re-upload the result. Updates the map's
        data_uri on success.

        :param map_obj: The map whose archive should be extracted.
        :raises MapProcessingError: If the zip cannot be extracted or restructured.
        :raises ClientError: If S3 download or upload fails.
        """
        start_time = time.monotonic()
        object_key = f"{map_obj.id}/{map_obj.zip_filename}"
        output_directory = object_key.rsplit(".", 1)[0]

        with NamedTemporaryFile(suffix=".zip") as temp_zip:
            logger.debug("[Map-Extraction]: '%s' (%d) — downloading archive.", map_obj.name, map_obj.id)
            self.aws_service.download_object(key=object_key, download_location=temp_zip.name)

            try:
                extracted = self.file_parser_service.extract_zip(temp_zip.name)
                restructured = self.file_parser_service.restructure_files(
                    extracted.files, extracted.root_dir
                )
                extracted_files = self.file_parser_service.remove_unwanted_extras(restructured, extracted.root_dir)
                final_files = self.file_parser_service.filter_extra_content(extracted_files, extracted.root_dir)

                total_mb = sum(f.stat().st_size for f in final_files) / (1024 * 1024)
            except (FileNotFoundError, BadZipFile, PermissionError) as exc:
                logger.error(
                    "[Map-Extraction]: Failed to extract '%s' (%d): %s",
                    map_obj.name, map_obj.id, exc,
                )
                raise MapProcessingError(
                    f"Failed to process map '{map_obj.id}': {exc}"
                ) from exc

            try:
                logger.info(
                    "[Map-Extraction]: Uploading %d file(s) for '%s' (%d).",
                    len(final_files),
                    map_obj.name,
                    map_obj.id,
                )
                s3_uri = self.aws_service.upload_directory_contents(
                    final_files, extracted.root_dir, output_directory
                )
                self.map_service.update_map(map_obj, data_uri=s3_uri)
            finally:
                extracted.temp_dir.cleanup()

        logger.info(
            "[Map-Extraction]: '%s' (%d) done — %d file(s), %.2f MB in %.2fs.",
            map_obj.name,
            map_obj.id,
            len(final_files),
            total_mb,
            time.monotonic() - start_time,
        )

    def reset_extracted_files(self) -> None:
        """
        (Temp) this function deletes all extracted map files from S3
        and resets their status back to 'DOWNLOADED' so they can be re-extracted.
        """
        maps = self.map_service.get_maps_with_data_uri()

        logger.info(
            "[Extraction-Cleanup]: Found %d map(s) with extracted files.",
            len(maps),
        )

        for map_obj in maps:
            try:
                base_name = map_obj.zip_filename.rsplit(".", 1)[0]
                prefix = f"{map_obj.id}/{base_name}/"

                deleted_count = self.aws_service.delete_prefix(prefix)

                logger.info(
                    "[Extraction-Cleanup]: Deleted %d file(s) for '%s' (%d)",
                    deleted_count,
                    map_obj.name,
                    map_obj.id,
                )

                self.map_service.update_map(
                    map_obj,
                    data_uri=None,
                    ingestion_status=IngestionStatus.DOWNLOADED,
                )

            except Exception:
                logger.exception(
                    "[Extraction-Cleanup]: Failed for '%s' (%d)",
                    map_obj.name,
                    map_obj.id,
                )

    def delete_zip_archives(self) -> None:
        """
        (Temp) Delete all zip archives from S3 for maps that have already been
        extracted. Safe to run since the extracted files are already in the bucket
        and the status is past DOWNLOADED.
        """
        maps = self.map_service.get_maps_with_data_uri()

        logger.info(
            "[Extraction-Cleanup]: Found %d map(s) with zip archives to delete.",
            len(maps),
        )

        for map_obj in maps:
            try:
                archive_key = f"{map_obj.id}/{map_obj.zip_filename}"
                self.aws_service.delete_object(key=archive_key)
                logger.info(
                    "[Extraction Cleanup]: Deleted archive '%s' for '%s' (%d).",
                    archive_key,
                    map_obj.name,
                    map_obj.id,
                )
            except Exception:
                logger.exception(
                    "[Extraction-Cleanup]: Failed to delete archive for '%s' (%d).",
                    map_obj.name,
                    map_obj.id,
                )
