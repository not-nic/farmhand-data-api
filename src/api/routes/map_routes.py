"""
API Routes for Farming Simulator Maps.

Routes:
    - GET /maps: Get all maps and their information.
    - GET /maps/{map_id}: Get a map by its ModHub ID.

Dependencies:
    - SessionDep: Database Session dependency.
"""

from fastapi import APIRouter, HTTPException, status

from src.api.core.dependencies import SessionDep
from src.api.core.logger import logger
from src.api.core.schema.maps.maps import MapModel, MapsResponse, MapUploadResponse
from src.api.services.aws_service import AwsService
from src.api.services.map_service import MapService

router = APIRouter(prefix="/maps", tags=["Maps"])


@router.get("/", status_code=status.HTTP_200_OK)
async def get_maps(
    db: SessionDep,
) -> MapsResponse:
    """
    Get all stored Farming Simulator maps.
    :param db: database session dependency
    :return: list of maps and their data.
    """
    try:
        maps = MapService(db).get_maps()
        return MapsResponse(maps=maps, count=len(maps))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{map_id}", status_code=status.HTTP_200_OK)
async def get_map_by_id(
    map_id: int,
    db: SessionDep,
) -> MapModel:
    """
    Get all stored Farming Simulator maps.
    :param map_id: the ModHub ID of the map.
    :param db: database session dependency
    :return: list of maps and their data.
    """
    try:
        map = MapService(db).get_map_by_id(map_id)

        if not map:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Map not found")

        return MapModel.model_validate(map)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/upload")
async def upload_default_map(map_request: MapModel, db: SessionDep) -> MapUploadResponse:
    """
    Upload a .zip file containing a 'default' map e.g. Riverbend springs to be
    ingested into the farmhand-data-api.
    :param map_request:
    :param db: database session dependency
    :return:
    """
    map_service = MapService(db)
    aws_service = AwsService()

    map_obj = map_service.create_map(map_request)
    logger.info("Creating map and presigned url for:'%s/%s'", map_obj.id, map_obj.zip_filename)

    url = aws_service.generate_pre_signed_url(str(map_obj.id), "put_object")
    return MapUploadResponse(id=map_obj.id, url=url)

