from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from src.api.core.dependencies import SessionDep
from src.api.core.schema.maps.farmlands import FarmlandRescaleRequest
from src.api.services.maps.farmlands.farmland_service import FarmlandService
from src.api.services.maps.map_extraction_service import MapExtractionService
from src.api.services.maps.map_ingestion_service import MapIngestionService
from src.api.services.maps.map_xml_parser_service import MapXmlParserService

router = APIRouter(prefix="/data", tags=["Data"])


@router.post("/reingest/{mod_id}", status_code=status.HTTP_202_ACCEPTED)
async def reingest_mod(
    mod_id: int,
    db: SessionDep,
    background_tasks: BackgroundTasks,
    mod_type: Literal["map"] = Query(default="map", description="The type of mod to reingest."),
):
    """
    Endpoint to manually trigger the re-ingestion (Download, Extraction, etc.)
    for a given mod.

    :param mod_id: The ModHub ID of the mod to reingest.
    :param mod_type: The type of mod to reingest e.g. 'map'.
    :param db: The database session dependency.
    :param background_tasks: The Background tasks dependency.
    """
    if mod_type == "map":
        background_tasks.add_task(MapIngestionService(db=db).reingest_map, mod_id)
        return {"message": f"Started re-ingest for map: '{mod_id}'"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{mod_type}' is not a valid mod_type."
        )


@router.post("/reingest", status_code=status.HTTP_202_ACCEPTED)
async def reingest_all_mods(
    db: SessionDep,
    background_tasks: BackgroundTasks,
    mod_type: Literal["map"] = Query(default="map", description="The type of mod to reingest."),
):
    """
    Endpoint to re-ingest every mod of the given type.

    Resets each mod to PENDING rather than reprocessing sequentially,
    letting the scheduled pipeline redrive them at its normal pace.
    :param mod_type: The type of mod to reingest e.g. 'map'.
    :param db: The database session dependency.
    :param background_tasks: The Background tasks dependency.
    """
    if mod_type == "map":
        background_tasks.add_task(MapIngestionService(db=db).reingest_all_maps)
        return {"message": "Started re-ingest for all maps"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{mod_type}' is not a valid mod_type."
        )


@router.post("/{mod_id}/rescale", status_code=status.HTTP_200_OK)
async def rescale_farmlands(
    mod_id: int,
    payload: FarmlandRescaleRequest,
    db: SessionDep,
):
    """
    Apply a linear scale+offset transform to a map's stored farmland
    coordinates.

    Intended to be used by a private frontend to the data-api to visually
    adjust a maps overview, farmland size, or any other data and overwrite it
    with a scaling factor.

    :param mod_id: The ModHub ID of the map whose farmlands to rescale.
    :param payload: The transform to apply, and whether to dry-run it.
    :param db: The database session dependency.
    """
    farmland_service: FarmlandService = FarmlandService(db)

    try:
        result: dict = farmland_service.rescale_farmlands(
            map_id=mod_id,
            offset_x=payload.offset_x,
            offset_y=payload.offset_y,
            scale_x=payload.scale_x,
            scale_y=payload.scale_y,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return result


@router.post("/parse-xml/{mod_id}", status_code=status.HTTP_200_OK)
async def parse_xml_for_map(
    mod_id: int,
    background_tasks: BackgroundTasks,
    db: SessionDep
):
    """
    (temp) Fetch and parse modDesc.xml and maps.xml directly from S3 for a
    single map, returning both parsed models as raw JSON. Does not persist
    anything — for inspecting parser output while testing.
    :param mod_id: The ModHub ID of the mod to parse.
    """
    map_xml_parser = MapXmlParserService(db=db)
    map_obj = map_xml_parser.map_service.get_map_by_id(mod_id)

    if not map_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No mod found with ID {mod_id}.",
        )

    background_tasks.add_task(map_xml_parser.parse_map, map_obj)
    return {"message": f"Started parsing modDesc.xml for map '{mod_id}'"}


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
