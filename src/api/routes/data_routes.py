from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from src.api.builder.farmland_builder import FarmlandBuilder
from src.api.constants import IngestionStatus
from src.api.core.dependencies import SessionDep
from src.api.core.schema.maps.farmlands import FarmlandRescaleRequest
from src.api.services.maps.map_ingestion_service import MapIngestionService
from src.api.services.maps.map_xml_parser_service import MapXmlParserService

router = APIRouter(prefix="/data", tags=["Data"])


@router.post("/reingest/{mod_id}", status_code=status.HTTP_202_ACCEPTED)
async def reingest_mod(
    mod_id: int,
    db: SessionDep,
    background_tasks: BackgroundTasks,
    mod_type: Literal["map"] = Query(default="map", description="The type of mod to reingest."),
    stage: Annotated[
        IngestionStatus, Query(description="The stage to re-ingest from.")
    ] = IngestionStatus.PENDING,
):
    """
    Manually trigger the re-ingestion of a given mod from a given stage.

    :param mod_id: (int) The ModHub ID of the mod to reingest.
    :param mod_type: (str) The type of mod to reingest e.g. 'map'.
    :param stage: (IngestionStatus) A stage to reingest from.
    :param db: The database session dependency.
    :param background_tasks: The Background tasks dependency.
    """
    if mod_type != "map":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{mod_type}' is not a valid mod_type."
        )

    if stage not in MapIngestionService.VALID_STAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reingest from stage '{stage.value}'.",
        )

    background_tasks.add_task(MapIngestionService(db=db).reingest_map, mod_id, stage)
    return {"message": f"Started re-ingest for map '{mod_id}' from stage '{stage.value}'"}


@router.post("/reingest", status_code=status.HTTP_202_ACCEPTED)
async def reingest_all_mods(
    db: SessionDep,
    background_tasks: BackgroundTasks,
    mod_type: Literal["map"] = Query(default="map", description="The type of mod to reingest."),
    stage: Annotated[
        IngestionStatus, Query(description="The stage to re-ingest from.")
    ] = IngestionStatus.PENDING,
):
    """
    Re-ingest every mod of a given type optionally starting from a later stage.

    :param mod_type: (str) The type of mod to reingest e.g. 'map'.
    :param stage: (IngestionStatus) A stage to reingest from.
    :param db: The database session dependency.
    :param background_tasks: The Background tasks dependency.
    """
    if mod_type != "map":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{mod_type}' is not a valid mod_type."
        )

    if stage not in MapIngestionService.VALID_STAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reingest from stage '{stage.value}'.",
        )

    background_tasks.add_task(MapIngestionService(db=db).reingest_all_maps, stage)
    return {"message": f"Started re-ingest for all maps from stage '{stage.value}'"}


@router.post("/{mod_id}/rescale", status_code=status.HTTP_200_OK)
async def rescale_farmlands(
    mod_id: int,
    payload: FarmlandRescaleRequest,
    db: SessionDep,
):
    """
    Apply a linear scale+offset transform to a map's stored farmland
    coordinates.

    Intended to be used by a frontend to the data-api to visually adjust
    a maps overview, farmland size, or any other data and overwrite it
    with a scaling factor.

    :param mod_id: The ModHub ID of the map whose farmlands to rescale.
    :param payload: The transform to apply, and whether to dry-run it.
    :param db: The database session dependency.
    """
    farmland_builder: FarmlandBuilder = FarmlandBuilder(db)

    try:
        result: dict = farmland_builder.rescale_farmlands(
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
    single map.
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
