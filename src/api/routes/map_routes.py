"""
API Routes for Farming Simulator Maps.

Routes:
    - GET /maps: Get all maps and their information.
    - GET /maps/{map_id}: Get a map by its ModHub ID.

Dependencies:
    - SessionDep: Database Session dependency.
"""

from fastapi import APIRouter, status, HTTPException

from src.api.core.dependencies import SessionDep
from src.api.core.schema.maps.maps import MapsResponse, MapModel
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
