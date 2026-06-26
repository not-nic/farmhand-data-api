from fastapi import APIRouter, BackgroundTasks, status

from src.api.core.dependencies import SessionDep
from src.api.services.maps.map_extraction_service import MapExtractionService
from src.api.services.maps.map_ingestion_service import MapIngestionService

router = APIRouter(prefix="/data", tags=["Data"])


@router.get("/extract", status_code=status.HTTP_200_OK)
async def extract_files_from_maps(db: SessionDep, background_tasks: BackgroundTasks):
    """
    (temp) Extract files from all DOWNLOADED maps in a background task.
    """
    background_tasks.add_task(MapIngestionService(db=db).extract_files_from_maps)
    return {"message": "Started extracting all DOWNLOADED maps"}


@router.get("/download", status_code=status.HTTP_200_OK)
async def download_pending_maps(db: SessionDep, background_tasks: BackgroundTasks):
    """
    (temp) Download all PENDING maps and store them in S3 in a background task.
    """
    background_tasks.add_task(MapIngestionService(db=db).download_pending_maps)
    return {"message": "Started downloading all PENDING maps"}


@router.get("/scrape", status_code=status.HTTP_200_OK)
async def scrape_new_maps(db: SessionDep, background_tasks: BackgroundTasks):
    """
    (temp) Scrape ModHub for new maps and set them to PENDING in a background task.
    """
    background_tasks.add_task(MapIngestionService(db=db).get_new_maps)
    return {"message": "Started scraping ModHub for new maps"}


@router.delete("/delete-extracted-files", status_code=status.HTTP_200_OK)
async def delete_extracted_files(
    db: SessionDep,
    background_tasks: BackgroundTasks,
):
    """
    (temp) Delete all extracted map files from S3.
    """
    background_tasks.add_task(
        MapExtractionService(db=db).reset_extracted_files
    )

    return {"message": "Started deleting extracted map files"}


@router.delete("/delete-zip-archives", status_code=status.HTTP_200_OK)
async def delete_zip_archives(
    db: SessionDep,
    background_tasks: BackgroundTasks,
):
    """
    (temp) Delete all zip archives from S3 for maps that have already been extracted.
    """
    background_tasks.add_task(MapExtractionService(db=db).delete_zip_archives)
    return {"message": "Started deleting zip archives from S3"}
