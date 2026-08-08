"""
Python module containing a parser for a farmlands.xml file.
"""

from xml.etree.ElementTree import Element

from src.api.core.schema.maps.farmlands import FarmlandsXmlModel, FarmlandXmlEntryModel
from src.api.parsers.xml.base_parser import BaseXmlParser


class FarmlandsXmlParser(BaseXmlParser[FarmlandsXmlModel]):
    """
    Parses a farmlands.xml file into a FarmlandsXmlModel.
    """

    def parse(self, content: bytes) -> FarmlandsXmlModel:
        """
        Parse farmlands.xml bytes into a FarmlandsXmlModel.

        :param content: Raw bytes of the farmlands.xml file from S3.
        :return: Parsed FarmlandsXmlModel.
        :raises ParseError: If the content is not valid XML.
        """
        root = self._load(content)
        farmlands_element = root.find("farmlands")

        if farmlands_element is None:
            return FarmlandsXmlModel()

        return FarmlandsXmlModel(
            price_per_ha=self._get_price_per_ha(farmlands_element),
            farmlands=self._get_farmlands(farmlands_element),
        )

    @staticmethod
    def _get_price_per_ha(farmlands_element: Element) -> float | None:
        """
        Get the map-wide price per hectare from the <farmlands> element.

        :param farmlands_element: The <farmlands> element.
        :return: The price per hectare, or None if not present.
        """
        price_per_ha = farmlands_element.get("pricePerHa")
        return float(price_per_ha) if price_per_ha is not None else None

    @staticmethod
    def _get_farmlands(farmlands_element: Element) -> list[FarmlandXmlEntryModel]:
        """
        Get every <farmland> entry from the <farmlands> element.

        :param farmlands_element: The <farmlands> element.
        :return: List of parsed FarmlandXmlEntryModel entries.
        """
        return [
            FarmlandXmlEntryModel(
                farmland_number=int(farmland.get("id")),
                price_scale=float(farmland.get("priceScale", 1.0)),
                default=farmland.get("defaultFarmProperty", "false") == "true",
            )
            for farmland in farmlands_element.findall("farmland")
            if farmland.get("id") is not None
        ]
