"""
API Routes for Scraping Data from ModHub.

This module defines the API routes for manually triggering scraping operations.
It allows the 'Service User' to scrape data from the ModHub.

Routes:
    - GET /scrape/{id}: Manually trigger scraping of an individual mod by its mod_id.
    - GET /scrape/maps: Manually trigger scraping of all maps from the ModHub website.

Dependencies:
    - is_service_user: Ensures that the request is coming from a service user.
"""

import tempfile

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from src.api.core.db.models import Map
from src.api.core.dependencies import SessionDep
from src.api.core.logger import logger
from src.api.core.repositories import MapRepository
from src.api.core.schema.maps.maps import MapModel
from src.api.core.schema.mods import ModModel
from src.api.services.aws_service import AwsService
from src.api.services.file_parser_service import FileParserService
from src.api.services.map_service import MapService
from src.api.services.modhub_service import ModHubService

router = APIRouter(prefix="/scrape", tags=["Scraper"])


@router.get("/mods/{id}", status_code=status.HTTP_202_ACCEPTED, response_model_by_alias=False)
async def scrape_mod(id: int) -> ModModel:
    """
    Function to manually trigger scraping of an individual mod by its mod_id.
    :param id: the mod_id in the ModHub URL
    :return: (202) Accepted and a message that the scraping has been started in the background.
    """
    mod_hub_service = ModHubService()
    return await mod_hub_service.scrape_mod(id)


@router.get("/maps", status_code=status.HTTP_202_ACCEPTED)
async def scrape_maps(background_tasks: BackgroundTasks, db: SessionDep) -> dict:
    """
    Function to manually trigger the scraping of maps from the Farming Simulator ModHub website.
    :param background_tasks: The background task to add the scrape function too.
    :param db: database session dependency
    :return: (202) Accepted and a message that the scraping has been started in the background.
    """
    map_service = MapService(db)
    background_tasks.add_task(map_service.scrape_maps)
    return {"detail": "Started scraping all maps from ModHub."}


@router.get("/maps/download", status_code=status.HTTP_200_OK)
async def download_maps(db: SessionDep, background_tasks: BackgroundTasks) -> dict:
    """
    (temp) Download all maps from the ModHub in a background task.
    """
    map_service = MapService(db)
    background_tasks.add_task(map_service.download_maps)
    return {"detail": "Started downloading all mods from modhub"}


@router.get("/maps/extract", status_code=status.HTTP_200_OK)
async def extract_files_from_maps(db: SessionDep, background_tasks: BackgroundTasks):
    """
    (temp) extract files from maps saved in the farmhand bucket in a background task.
    """
    map_service = MapService(db)
    background_tasks.add_task(map_service.extract_files)
    return {"message": "Started extracting all map data"}


@router.get("/maps/download/{id}", status_code=status.HTTP_200_OK)
async def scrape_and_download_map(id: int, db: SessionDep) -> MapModel:
    """
    (temp) method to download a mod and upload it to a bucket based
    on its ID.

    todo: move this to the service and improve it.
    """
    mod_hub_service = ModHubService()
    map_service = MapService(db)
    mod = await mod_hub_service.scrape_mod(id)

    try:
        mod_content = await mod_hub_service.download_mod(mod.file_url)
        aws_service = AwsService()
        aws_service.upload_object(mod_content, mod.id, mod.zip_filename)

        map_obj = MapModel(**mod.model_dump(mode="json"))

        map_service.create_map(map_obj)
        return map_obj

    except Exception as exc:
        raise HTTPException(detail=str(exc), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@router.get("/maps/extract/{id}", status_code=status.HTTP_200_OK)
async def extract_files_from_map(id: int, db: SessionDep):
    """
    (temp) method to extract map data files from a bucket.

    todo: move this to the service and improve it.
    """
    map_service = MapService(db)
    map_repository = MapRepository(db)
    map_obj: Map = map_service.get_map_by_id(id)
    aws_service = AwsService()

    object_key = f"{map_obj.id}/{map_obj.zip_filename}"

    with tempfile.NamedTemporaryFile(suffix=".zip") as temp_zip:
        logger.info(f"object_key: {object_key}")
        aws_service.download_object(key=object_key, download_location=temp_zip.name)

        file_parser_service = FileParserService()
        extracted = file_parser_service.extract_zip(temp_zip.name)
        updated_files = file_parser_service.restructure_files(extracted.files, extracted.root_dir)

        try:
            logger.info(f"Attempting to upload {len(extracted.files)} files to bucket...")
            output_directory = object_key.rsplit(".", 1)[0]
            s3_uri = aws_service.upload_directory_contents(
                updated_files, extracted.root_dir, output_directory
            )
            map_repository.update(map_obj.id, data_uri=s3_uri)
        finally:
            extracted.temp_dir.cleanup()

    return {"message": "map zip file contents uploaded"}
