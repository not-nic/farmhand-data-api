"""
API Routes for Farming Simulator Vehicles.

Routes:
    - POST /vehicles/ingest: Ingest the vehicle catalogue from a storeItems XML and vehicles .zip.
    - GET /vehicles: Get all vehicles, optionally filtered by category and brand.
    - GET /vehicles/categories: Get every vehicle category slug and label.
    - GET /vehicles/{id}: Get a vehicle by its ID.
"""

from uuid import UUID
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile

from fastapi import APIRouter, HTTPException, UploadFile, status

from src.api.constants import VehicleCategory
from src.api.core.db.models import Vehicle
from src.api.core.dependencies import SessionDep
from src.api.core.schema.vehicles import (
    VehicleCategoryResponseModel,
    VehicleIngestResult,
    VehicleResponseModel,
    VehiclesResponseModel,
)
from src.api.services.vehicles.vehicle_service import VehicleService

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


@router.post("/ingest", status_code=status.HTTP_201_CREATED)
async def ingest_vehicles(
    db: SessionDep,
    store_items: UploadFile,
    archive: UploadFile | None = None,
    l10n: UploadFile | None = None,
    store_configurations: UploadFile | None = None,
) -> VehicleIngestResult:
    """
    Ingest the vehicle catalogue into the database.

    :param db: Database session dependency.
    :param store_items: The storeItems XML file listing all vehicles.
    :param archive: (Optional) .zip archive of vehicle XML files for configurations.
    :param l10n: (Optional) The game's l10n XML, e.g. l10n_en.xml, for display labels.
    :param store_configurations: (Optional) storeConfigurations XML for translated
        motor and fill unit option names.
    :raises HTTPException: 400 if a file has the wrong extension or is not valid.
    """
    if not store_items.filename or not store_items.filename.lower().endswith(".xml"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="store_items must be an .xml file.",
        )

    if archive is not None and (
        not archive.filename or not archive.filename.lower().endswith(".zip")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="archive must be a .zip file.",
        )

    for field, upload in (("l10n", l10n), ("store_configurations", store_configurations)):
        if upload is not None and (
            not upload.filename or not upload.filename.lower().endswith(".xml")
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field} must be an .xml file.",
            )

    store_items_content = await store_items.read()
    archive_content = await archive.read() if archive is not None else None
    l10n_content = await l10n.read() if l10n is not None else None
    store_configurations_content = (
        await store_configurations.read() if store_configurations is not None else None
    )

    try:
        return VehicleService(db).ingest(
            store_items_content, archive_content, l10n_content, store_configurations_content
        )
    except BadZipFile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="archive is not a valid .zip file.",
        )
    except ParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An uploaded XML file is not valid XML: {exc}",
        )


@router.get("/categories")
async def get_vehicle_categories() -> list[VehicleCategoryResponseModel]:
    """
    Endpoint to get every vehicle shop category, with its slug and display label,
    e.g. {"slug": "medium_tractors", "label": "Medium Tractors"}.

    Declared before GET /{id} so "/vehicles/categories" is not parsed as a UUID.

    :return: Category slugs and labels, sorted by label. Each slug is usable
        directly as the 'category' query parameter on GET /vehicles.
    """
    return sorted(
        (
            VehicleCategoryResponseModel(slug=category.slug, label=category.value)
            for category in VehicleCategory
        ),
        key=lambda category: category.label,
    )


@router.get("/{id}")
async def get_vehicle(db: SessionDep, id: UUID) -> VehicleResponseModel:
    """
    Endpoint to get a vehicle by its ID.

    :param db: Database session dependency.
    :param id: The ID of a vehicle.
    :return: A Vehicle object if it exists.
    """
    vehicle: Vehicle = VehicleService(db).get_vehicle_by_id(id)

    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found.",
        )

    return VehicleResponseModel.from_vehicle(vehicle)


@router.get("/")
async def get_all_vehicles(
    db: SessionDep, category: str | None = None, brand: str | None = None
) -> VehiclesResponseModel:
    """
    Endpoint to get all vehicles, optionally filtered.

    :param db: Database session dependency.
    :param category: (Optional) category slug (e.g. "medium_tractors"), label,
        or raw key, e.g. "Medium Tractors"/"TRACTORSM".
    :param brand: (Optional) display brand, e.g. "John Deere".
    :return: A list of matching Vehicle objects.
    """
    vehicles: list[Vehicle] = VehicleService(db).filter_vehicles(category=category, brand=brand)

    return VehiclesResponseModel(
        vehicles=[VehicleResponseModel.from_vehicle(v) for v in vehicles]
    )
