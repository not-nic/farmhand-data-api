"""
Parser for Farming Simulator maps.xml files.
"""

from xml.etree.ElementTree import Element

from src.api.core.schema.maps.maps_xml import (
    AnimalsModel,
    MapsXmlModel,
)
from src.api.parsers.xml.base_parser import BaseXmlParser


class MapsXmlParser(BaseXmlParser[MapsXmlModel]):
    """
    Parses a Farming Simulator maps.xml file into a MapsXmlModel.
    """

    def parse(self, content: bytes) -> MapsXmlModel:
        """
        Parse maps.xml bytes and return a MapsXmlModel.

        :param content: Raw bytes of the maps.xml file from S3.
        :return: Parsed MapsXmlModel.
        :raises ParseError: If the content is not valid XML.
        """
        root = self._load(content)

        return MapsXmlModel(
            width=int(root.get("width", 0)),
            height=int(root.get("height", 0)),
            overview_filename=root.get("imageFilename"),
            map_i3d_filename=self._text(root, "filename"),
            farmlands_filename=self._attr(root, "farmlands", "filename"),
            fields_filename=self._attr(root, "fields", "filename"),
            fill_types_filename=self._attr(root, "fillTypes", "filename"),
            animals=self._get_animals(root),
        )

    def _get_animals(self, root: Element) -> AnimalsModel | None:
        """
        Extract the <animals> element's file references.

        :param root: The root <map> element.
        :return: AnimalsModel, or None if the map has no <animals> element.
        """
        animals_element = root.find("animals")
        if animals_element is None:
            return None

        return AnimalsModel(
            filename=animals_element.get("filename"),
            food_filename=self._attr(animals_element, "food", "filename"),
        )
