from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from src.api.builder.farmland_builder import FarmlandBuilder
from src.api.constants import IngestionStatus, XmlHandler
from src.api.core.dependencies import SessionDep
from src.api.core.schema.maps.farmlands import FarmlandRescaleRequest
from src.api.services.maps.map_ingestion_service import MapIngestionService

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
    handlers: Annotated[
        list[XmlHandler] | None,
        Query(description="Only re-run these XML handlers. Requires stage=EXTRACTED."),
    ] = None,
):
    """
    Manually trigger the re-ingestion of a given mod from a given stage.

    :param mod_id: (int) The ModHub ID of the mod to reingest.
    :param mod_type: (str) The type of mod to reingest e.g. 'map'.
    :param stage: (IngestionStatus) A stage to reingest from.
    :param handlers: (list[XmlHandler] | None) Only re-run these XML handlers.
        Requires stage=EXTRACTED.
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

    handlers = handlers or None

    if handlers and stage != IngestionStatus.EXTRACTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Handlers can only be selected when reingesting from stage 'EXTRACTED'.",
        )

    background_tasks.add_task(MapIngestionService(db=db).reingest_map, mod_id, stage, handlers)

    message = f"Started re-ingest for map '{mod_id}' from stage '{stage.value}'"
    if handlers:
        message += f" (handlers: {', '.join(h.value for h in handlers)})"
    return {"message": message}


@router.post("/reingest", status_code=status.HTTP_202_ACCEPTED)
async def reingest_all_mods(
    db: SessionDep,
    background_tasks: BackgroundTasks,
    mod_type: Literal["map"] = Query(default="map", description="The type of mod to reingest."),
    stage: Annotated[
        IngestionStatus, Query(description="The stage to re-ingest from.")
    ] = IngestionStatus.PENDING,
    handlers: Annotated[
        list[XmlHandler] | None,
        Query(description="Only re-run these XML handlers. Requires stage=EXTRACTED."),
    ] = None,
):
    """
    Re-ingest every mod of a given type optionally starting from a later stage.

    :param mod_type: (str) The type of mod to reingest e.g. 'map'.
    :param stage: (IngestionStatus) A stage to reingest from.
    :param handlers: (list[XmlHandler] | None) Only re-run these XML handlers.
        Requires stage=EXTRACTED.
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

    handlers = handlers or None

    if handlers and stage != IngestionStatus.EXTRACTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Handlers can only be selected when reingesting from stage 'EXTRACTED'.",
        )

    background_tasks.add_task(MapIngestionService(db=db).reingest_all_maps, stage, handlers)

    message = f"Started re-ingest for all maps from stage '{stage.value}'"
    if handlers:
        message += f" (handlers: {', '.join(h.value for h in handlers)})"
    return {"message": message}


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
