"""
Vehicle Service Module used for CRUD access to Farming Simulator vehicles,
and for ingesting the vehicle catalogue from a storeItems file and vehicles archive.
"""

from io import BytesIO
from uuid import UUID
from xml.etree.ElementTree import ParseError
from zipfile import ZipFile

from sqlalchemy.orm import Session

from src.api.constants import AssetType, ContentType
from src.api.core.config import settings
from src.api.core.db.models import Vehicle
from src.api.core.logger import logger
from src.api.core.repositories import AssetRepository, VehicleRepository
from src.api.core.schema.vehicles import (
    FillUnitConfigModel,
    MotorConfigModel,
    VehicleIngestResult,
    VehicleXmlModel,
)
from src.api.parsers.xml.vehicles.l10n_parser import L10n, L10nXmlParser
from src.api.parsers.xml.vehicles.store_configurations_parser import (
    StoreConfigurationsXmlParser,
)
from src.api.parsers.xml.vehicles.store_items_parser import StoreItemsXmlParser
from src.api.parsers.xml.vehicles.vehicle_xml_parser import VehicleXmlParser
from src.api.services.aws.aws_service import AwsService
from src.api.utils import normalise_config_path, strip_dlc_prefix


class VehicleService:
    """
    Vehicle Service used for reading vehicles and ingesting the vehicle
    catalogue into the database.
    """

    def __init__(
        self,
        db: Session,
        ingest_bucket: AwsService | None = None,
        assets_bucket: AwsService | None = None,
    ):
        """
        Constructor for the vehicle service.
        :param db: Database Session.
        :param ingest_bucket: AWS service for the ingest bucket, holds the raw .dds images.
        :param assets_bucket: AWS service for the assets bucket, only used to build asset URIs.
        """
        self.db = db
        self.vehicle_repository = VehicleRepository(db)
        self.asset_repository = AssetRepository(db)
        self.ingest_bucket = ingest_bucket or AwsService()
        self.assets_bucket = assets_bucket or AwsService(
            bucket_name=settings.AWS_S3_ASSETS_BUCKET_NAME
        )

    def get_vehicles(self) -> list[Vehicle]:
        """
        Get all vehicles.
        :return: List of vehicles.
        """
        return self.vehicle_repository.all()

    def filter_vehicles(self, category: str | None = None, brand: str | None = None) -> list[Vehicle]:
        """
        Get vehicles, optionally filtered by category and/or brand.
        :param category: Category slug, label, or raw key, e.g. "medium_tractors",
            "Medium Tractors", or "TRACTORSM".
        :param brand: Display brand, e.g. "John Deere".
        :return: Matching vehicles.
        """
        return self.vehicle_repository.filter(category=category, brand=brand)

    def get_vehicle_by_config_path(self, config_path: str) -> Vehicle | None:
        """
        Get a vehicle by its config_path.
        :param config_path: The path to the vehicle's XML config file.
        :return: (Optional) the vehicle if it exists.
        """
        return self.vehicle_repository.get_by_config_path(config_path)

    def get_vehicle_by_id(self, vehicle_id: UUID) -> Vehicle | None:
        """
        Get a vehicle by its ids.
        :param vehicle_id: The ID of a vehicle.
        :return: (Optional) the vehicle if it exists.
        """
        return self.vehicle_repository.get_by_id(vehicle_id)

    def ingest(
        self,
        store_items: bytes,
        archive: bytes | None = None,
        l10n: bytes | None = None,
        store_configurations: bytes | None = None,
    ) -> VehicleIngestResult:
        """
        Ingest the vehicle catalogue. The store items file decides which vehicles
        exist, the optional archive adds type, image and configurations.

        :param store_items: Raw bytes of a storeItems XML file.
        :param archive: Raw bytes of a .zip of vehicle XML files, if any.
        :param l10n: Raw bytes of the game's l10n XML for display labels, if any.
            Without it labels fall back to key-derived labels.
        :param store_configurations: Raw bytes of a storeConfigurations XML, if any. Its
            translated motor and fill unit option names and prices win over the vehicle XML.
        :return: A summary of the ingest.
        :raises ParseError: If any of the XML files are not valid XML.
        :raises BadZipFile: If the archive is not a valid zip.
        """
        items = StoreItemsXmlParser().parse(store_items)
        texts = L10nXmlParser().parse(l10n) if l10n is not None else L10n()
        store_configs = (
            StoreConfigurationsXmlParser().parse(store_configurations)
            if store_configurations is not None
            else {}
        )
        parsed_xml: dict[str, VehicleXmlModel] = {}
        failures = 0
        assets_registered = 0

        if archive is not None:
            parsed_xml, failures = self._parse_archive(archive)

        archive_file = ZipFile(BytesIO(archive)) if archive is not None else None
        with_configurations = 0
        for item in items:
            # DLC items are keyed "pdlc/<pack>/vehicles/...", the archive holds "vehicles/...".
            xml = parsed_xml.get(item.config_path) or parsed_xml.get(
                strip_dlc_prefix(item.config_path)
            )
            store_motors, store_fill_units = store_configs.get(item.config_path, ([], []))
            incoming = Vehicle(
                config_path=item.config_path,
                name=item.name,
                brand=item.brand,
                category=item.category,
                category_label=texts.category(item.category) if item.category else None,
                price=item.price,
                dlc=item.dlc,
            )
            xml_motors = xml.motor_configurations if xml else []
            xml_fill_units = xml.fill_unit_configurations if xml else []
            motors = [m.model_dump() for m in self._merge_motors(store_motors, xml_motors)]
            fill_units = [
                self._label_fill_units(f.model_dump(), texts)
                for f in self._merge_fill_units(store_fill_units, xml_fill_units)
            ]
            if xml:
                with_configurations += 1
                incoming.vehicle_type = xml.vehicle_type
                incoming.image = xml.image
                incoming.weight = xml.weight
                incoming.working_speed = xml.working_speed
                incoming.working_width = xml.working_width
                incoming.needed_power = xml.needed_power

            vehicle = self.vehicle_repository.upsert_by_config_path(incoming, commit=False)
            if xml or store_motors:
                self.vehicle_repository.replace_configurations(
                    vehicle, motors, fill_units, commit=False
                )
            if archive_file is not None and vehicle.image:
                assets_registered += self._register_store_image(vehicle, archive_file)

        if archive_file is not None:
            archive_file.close()
        self.db.commit()

        result = VehicleIngestResult(
            store_items=len(items),
            vehicles_upserted=len(items),
            with_configurations=with_configurations,
            xml_failures=failures,
            assets_registered=assets_registered,
        )
        logger.info("[VehicleService]: Ingested vehicle catalogue: %s", result.model_dump())
        return result

    @staticmethod
    def _merge_motors(
        store: list[MotorConfigModel], xml: list[MotorConfigModel]
    ) -> list[MotorConfigModel]:
        """
        Prefer the storeConfigurations motors (translated, complete for DLC), filling
        fields they lack (e.g. max speed) from the vehicle XML motor of the same index.
        :param store: Motors from storeConfigurations.
        :param xml: Motors from the vehicle XML.
        :return: The merged motors.
        """
        if not store:
            return xml
        by_index = {m.index: m for m in xml}
        merged = []
        for motor in store:
            fallback = by_index.get(motor.index)
            if fallback:
                motor = motor.model_copy(
                    update={k: v for k, v in fallback.model_dump().items()
                            if getattr(motor, k) is None}
                )
            merged.append(motor)
        return merged

    @staticmethod
    def _merge_fill_units(
        store: list[FillUnitConfigModel], xml: list[FillUnitConfigModel]
    ) -> list[FillUnitConfigModel]:
        """
        Keep the vehicle XML fill unit configurations (only they hold the contents), using
        the translated name and price from storeConfigurations for the same index.
        :param store: Fill unit options from storeConfigurations.
        :param xml: Fill unit configurations from the vehicle XML.
        :return: The merged configurations.
        """
        by_index = {f.index: f for f in store}
        return [
            config.model_copy(update={"name": option.name, "price": option.price})
            if (option := by_index.get(config.index))
            else config
            for config in xml
        ]

    @staticmethod
    def _label_fill_units(config: dict, texts: L10n) -> dict:
        """
        :param config: A dumped FillUnitConfigModel.
        :param texts: The l10n lookup.
        :return: The config with each fill type as {"key": ..., "label": ...}.
        """
        for unit in config["fill_units"]:
            unit["fill_types"] = [
                {"key": key, "label": texts.fill_type(key)} for key in unit["fill_types"]
            ]
        return config

    def _register_store_image(self, vehicle: Vehicle, archive: ZipFile) -> int:
        """
        Upload a vehicle's raw store image to the ingest bucket and register an
        icon asset for the conversion job. Nothing is uploaded when the image is
        already registered and ingested at the same URI.
        :param vehicle: The upserted vehicle, with its source image path set.
        :param archive: The open vehicles archive containing the .dds images.
        :return: 1 if an asset was registered, else 0 (no image in the archive).
        """
        stem = vehicle.image.rsplit(".", 1)[0]
        archive_stem = strip_dlc_prefix(stem)
        entry = self._find_entry(archive, f"{archive_stem}.dds")
        is_png = entry is None
        if is_png:
            entry = self._find_entry(archive, f"{archive_stem}.png")
        if entry is None:
            logger.warning(
                "[VehicleService]: No store image '%s.dds/.png' in archive for '%s'.",
                archive_stem, vehicle.config_path,
            )
            return 0

        asset_key = f"{stem}.png"
        asset_uri = self.assets_bucket.build_uri(asset_key)
        existing = self.asset_repository.get_by_vehicle_and_type(
            vehicle.id, AssetType.ICON
        )
        up_to_date = existing is not None and existing.asset_uri == asset_uri and existing.is_ingested

        if not up_to_date and is_png:
            # Already a .png (e.g. DLC images from the website), no conversion needed.
            self.assets_bucket.put_object(
                key=asset_key, body=archive.read(entry), content_type=ContentType.PNG
            )
            up_to_date = True
        elif not up_to_date:
            self.ingest_bucket.put_object(key=entry, body=archive.read(entry))

        self.asset_repository.upsert_vehicle_asset(
            vehicle_id=vehicle.id,
            asset_type=AssetType.ICON,
            filename=entry,
            asset_uri=asset_uri,
            is_ingested=up_to_date,
            commit=False,
        )
        return 1

    @staticmethod
    def _find_entry(archive: ZipFile, path: str) -> str | None:
        """
        Find a zip entry by path, ignoring case.
        :param archive: The open zip archive.
        :param path: The wanted entry path.
        :return: The entry name as stored in the archive, or None.
        """
        names = archive.namelist()
        if path in names:
            return path
        lowered = path.lower()
        return next((name for name in names if name.lower() == lowered), None)

    @staticmethod
    def _parse_archive(archive: bytes) -> tuple[dict[str, VehicleXmlModel], int]:
        """
        Parse every vehicle XML in a zip archive, resolving reskin parents within it.
        :param archive: Raw bytes of the zip archive.
        :return: Parsed models by canonical config path, and the number of failed files.
        :raises BadZipFile: If the archive is not a valid zip.
        """
        parser = VehicleXmlParser()
        parsed: dict[str, VehicleXmlModel] = {}
        failures = 0

        with ZipFile(BytesIO(archive)) as zf:
            index: dict[str, str] = {}
            for name in zf.namelist():
                if not name.lower().endswith(".xml"):
                    continue
                path = normalise_config_path(name)
                if path is not None:
                    index[path] = name

            def resolve(path: str) -> bytes | None:
                entry = index.get(path) or index.get(strip_dlc_prefix(path))
                return zf.read(entry) if entry else None

            for path, entry in index.items():
                try:
                    parsed[path] = parser.parse(zf.read(entry), resolve)
                except ValueError as exc:
                    # Not a vehicle definition (e.g. sound or shared XML files).
                    logger.debug("[VehicleService]: Skipped '%s': %s", entry, exc)
                except ParseError as exc:
                    failures += 1
                    logger.warning("[VehicleService]: Failed to parse '%s': %s", entry, exc)

        return parsed, failures
