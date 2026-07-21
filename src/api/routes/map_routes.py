"""
API Routes for Farming Simulator Maps.

Routes:
    - GET /maps: Get all maps and their information.
    - GET /maps/{map_id}: Get a map by its ModHub ID.
"""

from fastapi import APIRouter, HTTPException, status

from src.api.core.dependencies import SessionDep
from src.api.core.schema.maps import (
    MapResponse,
    MapsResponse,
)
from src.api.services.maps.map_service import MapService

router = APIRouter(prefix="/maps", tags=["Maps"])


@router.get("/", status_code=status.HTTP_200_OK)
async def get_maps(db: SessionDep) -> MapsResponse:
    """
    Get all stored Farming Simulator maps.
    :param db: Database session dependency.
    :return: List of maps and their data.
    """
    try:
        maps = MapService(db).get_maps()
        return MapsResponse(
            maps=[MapResponse.model_validate(m) for m in maps],
            count=len(maps),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{map_id}", status_code=status.HTTP_200_OK)
async def get_map_by_id(map_id: int, db: SessionDep) -> MapResponse:
    """
    Get a single Farming Simulator map by its ModHub ID.
    :param map_id: The ModHub ID of the map.
    :param db: Database session dependency.
    :return: Map and its data.
    """
    try:
        map_obj = MapService(db).get_map_by_id(map_id)

        if not map_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Map not found.")

        return MapResponse.model_validate(map_obj)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

