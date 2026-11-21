"""
Python module containing a handler for Farming Simulator map vehicles.xml files.
"""

from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

from src.api.constants import XmlHandler
from src.api.core.db.models import Map, MapVehicle
from src.api.core.logger import logger
from src.api.core.repositories import MapVehicleRepository, VehicleRepository
from src.api.core.schema.vehicles.map_vehicles import MapVehicleModel
from src.api.handlers.xml.base_xml_handler import BaseXmlHandler
from src.api.parsers.xml.vehicles.map_vehicles_parser import MapVehiclesXmlParser
from src.api.services.assets.assets_service import AssetsService
from src.api.services.aws.aws_service import AwsService
from src.api.utils import normalise_config_path


class VehiclesXmlHandler(BaseXmlHandler[list[MapVehicleModel]]):
    """
    Handler class used for processing and persisting a farming simulator map's
    'vehicles.xml' (starting equipment), linking it to catalogue vehicles.
    """

    key = XmlHandler.VEHICLES

    def __init__(
            self,
            db: Session,
            aws_service: AwsService,
            assets_service: AssetsService | None = None,
    ) -> None:
        super().__init__(db, aws_service, assets_service)
        self.vehicle_repository = VehicleRepository(db)
        self.map_vehicle_repository = MapVehicleRepository(db)

    def process(self, map_obj: Map) -> None:
        """
        Get, parse, and persist a vehicles.xml for the given map.
        :param map_obj: The map to process.
        """
        if not map_obj.data_uri:
            logger.warning(
                "[VehiclesXml-Handler]: Skipped '%s' (%d) — no data_uri.",
                map_obj.name,
                map_obj.id,
            )
            return

        if not map_obj.mod_description or not map_obj.mod_description.vehicles_filename:
            logger.warning(
                "[VehiclesXml-Handler]: Skipped '%s' (%d) — no vehicles_filename, "
                "ModDescHandler must run first.",
                map_obj.name,
                map_obj.id,
            )
            return

        vehicles_filename = map_obj.mod_description.vehicles_filename
        try:
            content = self._get(f"{map_obj.data_uri}/config/{vehicles_filename}")
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") not in ("NoSuchKey", "404"):
                raise
            logger.warning(
                "[VehiclesXml-Handler]: Skipped '%s' (%d) — '%s' not found in config/.",
                map_obj.name,
                map_obj.id,
                vehicles_filename,
            )
            return
        parsed: list[MapVehicleModel] = MapVehiclesXmlParser().parse(content)
        self._store(map_obj, parsed)

    def _store(self, map_obj: Map, parsed: list[MapVehicleModel], **kwargs) -> None:
        """
        Persist the starting vehicles of a map, replacing any existing ones.

        :param map_obj: The parent map.
        :param parsed: The parsed list of MapVehicleModel.
        """
        entries: list[tuple[str, MapVehicleModel]] = []
        skipped = 0
        other_farm = 0
        for item in parsed:
            if not item.is_starting_farm:
                other_farm += 1
                continue
            config_path = normalise_config_path(item.filename)
            if config_path is None:
                skipped += 1
                continue
            entries.append((config_path, item))

        known = self.vehicle_repository.get_by_config_paths(path for path, _ in entries)

        rows: list[MapVehicle] = []
        unknown = 0
        for config_path, item in entries:
            vehicle = known.get(config_path)
            if vehicle is None:
                unknown += 1
                logger.debug(
                    "[VehiclesXml-Handler]: Unknown vehicle '%s' for '%s' (%d).",
                    config_path,
                    map_obj.name,
                    map_obj.id,
                )
                continue

            motor = self._select(vehicle.motor_configurations, item.configurations.get("motor"))
            fill_unit = self._select(
                vehicle.fill_unit_configurations, item.configurations.get("fillUnit")
            )
            rows.append(
                MapVehicle(
                    vehicle_id=vehicle.id,
                    motor_configuration_id=motor.id if motor else None,
                    fill_unit_configuration_id=fill_unit.id if fill_unit else None,
                )
            )

        self.map_vehicle_repository.replace_for_map(map_obj.id, rows)

        logger.info(
            "[VehiclesXml-Handler]: '%s' (%d) — linked %d vehicle(s), skipped %d on other farms, "
            "%d mod/non-vehicle, %d unknown.",
            map_obj.name,
            map_obj.id,
            len(rows),
            other_farm,
            skipped,
            unknown,
        )

    @staticmethod
    def _select(configs: list, configuration_id: str | None):
        """
        Pick the configuration whose 1-based index matches a configuration id.
        :param configs: The vehicle's configuration rows.
        :param configuration_id: The raw id from vehicles.xml, ignored if not an integer.
        :return: The matching configuration, or None.
        """
        if configuration_id is None or not configuration_id.isdigit():
            return None
        index = int(configuration_id)
        return next((c for c in configs if c.index == index), None)
