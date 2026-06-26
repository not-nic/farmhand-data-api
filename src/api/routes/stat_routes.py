"""
API Routes for status about ingested Farming Simulator Maps.

Routes:

Dependencies:
    - SessionDep: Database Session dependency.
"""

from fastapi import APIRouter
from pydantic import BaseModel, computed_field

from src.api.core.dependencies import SessionDep
from src.api.services.aws_service import AwsService
from src.api.services.maps.map_service import MapService

router = APIRouter(prefix="/stats", tags=["Stats"])


class MapStorageStats(BaseModel):
    map_id: int
    map_name: str
    zip_size_mb: float | None
    extracted_size_mb: float | None

    @computed_field
    @property
    def total_size_mb(self) -> float:
        return round((self.zip_size_mb or 0) + (self.extracted_size_mb or 0), 2)


class BucketStorageResponse(BaseModel):
    maps: list[MapStorageStats]
    total_zip_size_mb: float
    total_extracted_size_mb: float
    total_size_mb: float
    map_count: int


@router.get("/storage", response_model=BucketStorageResponse, status_code=200)
async def get_storage_stats(db: SessionDep):
    """
    Inspect the S3 bucket and return a per-map breakdown of zip archive size
    and combined extracted file size, sorted by total size descending.
    """
    maps = MapService(db).get_maps()
    aws_service = AwsService()
    stats: list[MapStorageStats] = []

    for map_obj in maps:
        objects = aws_service.list_objects(prefix=f"{map_obj.id}/")

        zip_bytes = sum(
            size for key, size in objects
            if key == f"{map_obj.id}/{map_obj.zip_filename}"
        )
        extracted_bytes = sum(
            size for key, size in objects
            if key != f"{map_obj.id}/{map_obj.zip_filename}"
        )

        stats.append(MapStorageStats(
            map_id=map_obj.id,
            map_name=map_obj.name,
            zip_size_mb=round(zip_bytes / (1024 * 1024), 2) if zip_bytes else None,
            extracted_size_mb=round(extracted_bytes / (1024 * 1024), 2) if extracted_bytes else None,
        ))

    stats.sort(key=lambda s: s.total_size_mb, reverse=True)

    return BucketStorageResponse(
        maps=stats,
        total_zip_size_mb=round(sum(s.zip_size_mb or 0 for s in stats), 2),
        total_extracted_size_mb=round(sum(s.extracted_size_mb or 0 for s in stats), 2),
        total_size_mb=round(sum(s.total_size_mb for s in stats), 2),
        map_count=len(stats),
    )
