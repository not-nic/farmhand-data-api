from fastapi import APIRouter, BackgroundTasks, status

from src.api.core.dependencies import SessionDep
from src.api.services.maps.map_extraction_service import MapExtractionService

router = APIRouter(prefix="/data", tags=["Data"])


@router.get("/extract", status_code=status.HTTP_200_OK)
async def extract_files_from_maps(db: SessionDep, background_tasks: BackgroundTasks):
    """
    (temp) extract files from maps saved in the farmhand bucket in a background task.
    """
    map_extraction_service = MapExtractionService(db)
    background_tasks.add_task(map_extraction_service.extract_files_from_all_maps)
    return {"message": "Started extracting all map data"}
