"""
Parser for Farming Simulator storeConfigurations XML files (e.g. storeConfigurations_en.xml),
exported by the game with configuration names already translated.
"""

from xml.etree.ElementTree import Element

from src.api.core.schema.vehicles.vehicle_xml import FillUnitConfigModel, MotorConfigModel
from src.api.parsers.xml.base_parser import BaseXmlParser
from src.api.utils import normalise_config_path


class StoreConfigurationsXmlParser(
    BaseXmlParser[dict[str, tuple[list[MotorConfigModel], list[FillUnitConfigModel]]]]
):
    """
    Parses a storeConfigurations XML file into motor and fill unit options per vehicle.
    Fill unit options carry only their name and price, the contents come from the vehicle XML.
    """

    def parse(
        self, content: bytes
    ) -> dict[str, tuple[list[MotorConfigModel], list[FillUnitConfigModel]]]:
        """
        :param content: Raw bytes of the storeConfigurations XML file.
        :return: (motors, fill units) keyed by canonical config path.
        :raises ParseError: If the content is not valid XML.
        """
        root = self._load(content)
        items: dict[str, tuple[list[MotorConfigModel], list[FillUnitConfigModel]]] = {}
        for item in root.findall("item"):
            config_path = normalise_config_path(item.get("xmlFilename", ""))
            if config_path is None:
                continue
            motors = [
                MotorConfigModel(
                    index=int(option.get("index")),
                    name=option.get("name") or None,
                    vehicle_name=option.get("vehicleName") or None,
                    hp=self._to_int(option.get("power")),
                    max_speed=self._to_int(option.get("maxSpeed")),
                    price=self._to_int(option.get("price")),
                )
                for option in self._options(item, "motor")
            ]
            fill_units = [
                FillUnitConfigModel(
                    index=int(option.get("index")),
                    # Unnamed options get a placeholder name of their index, e.g. "1".
                    name=(
                        None
                        if option.get("hasDefaultName", "false").lower() == "true"
                        else option.get("name") or None
                    ),
                    price=self._to_int(option.get("price")),
                )
                for option in self._options(item, "fillUnit")
            ]
            if motors or fill_units:
                items[config_path] = (motors, fill_units)
        return items

    @staticmethod
    def _options(item: Element, name: str) -> list[Element]:
        """
        :param item: An <item> element.
        :param name: The configuration name, e.g. "motor".
        :return: All options of that configuration, including unselectable ones, as a
            map's vehicles.xml can still reference them by index.
        """
        return [
            option
            for option in item.findall(f"configuration[@name='{name}']/option")
            if option.get("index")
        ]

    @staticmethod
    def _to_int(value: str | None) -> int | None:
        """
        :param value: A numeric string.
        :return: The rounded integer, or None if missing / not numeric.
        """
        try:
            return round(float(value)) if value not in (None, "") else None
        except ValueError:
            return None
