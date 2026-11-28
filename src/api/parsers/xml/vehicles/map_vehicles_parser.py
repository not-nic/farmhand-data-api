"""
Parser for a map's (or save game's) vehicles.xml file.
"""

from src.api.core.schema.vehicles.map_vehicles import MapVehicleModel
from src.api.parsers.xml.base_parser import BaseXmlParser


class MapVehiclesXmlParser(BaseXmlParser[list[MapVehicleModel]]):
    """
    Parses a vehicles.xml file into a list of MapVehicleModel.
    """

    def parse(self, content: bytes) -> list[MapVehicleModel]:
        """
        Parse vehicles.xml bytes.

        :param content: Raw bytes of the vehicles.xml file (a UTF-8 BOM is tolerated).
        :return: List of starting vehicles, in file order.
        :raises ParseError: If the content is not valid XML.
        """
        root = self._load(content.removeprefix(b"\xef\xbb\xbf"))
        vehicles: list[MapVehicleModel] = []

        for vehicle in root.findall("vehicle"):
            filename = vehicle.get("filename")
            if not filename:
                continue

            configurations = {
                c.get("name"): c.get("id", "")
                for c in vehicle.findall("configuration")
                if c.get("name")
            }

            farm_id = vehicle.get("farmId")
            vehicles.append(
                MapVehicleModel(
                    filename=filename,
                    farm_id=int(farm_id) if farm_id and farm_id.lstrip("-").isdigit() else None,
                    configurations=configurations,
                )
            )

        return vehicles
