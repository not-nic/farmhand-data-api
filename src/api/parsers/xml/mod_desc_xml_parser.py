"""
Parser for Farming Simulator modDesc.xml files.

modDesc.xml is the root file for each Farming Simulator mod. It contains the config
file paths, which are used to extract information from them, plus some basic
information usually found on the ModHub, i.e. Descriptions, Dependencies.
"""

from xml.etree.ElementTree import Element

from src.api.core.logger import logger
from src.api.core.schema.mods.mod_desc import MapConfigModel, ModDescModel
from src.api.parsers.xml.base_parser import BaseXmlParser


class ModDescXmlParser(BaseXmlParser[ModDescModel]):
    """
    Parses a Farming Simulator modDesc.xml file into a ModDescModel.
    """

    _PREFERRED_LOCALES = ("en",)

    def parse(self, content: bytes) -> ModDescModel:
        """
        Parse modDesc.xml bytes and return a ModDescModel.

        :param content: Raw bytes of the modDesc.xml file from S3.
        :return: Parsed ModDescModel.
        :raises ParseError: If the content is not valid XML.
        """
        root = self._load(content)

        model = ModDescModel(
            title=self._localised_text(root, "title"),
            description=self._localised_text(root, "description"),
            icon_filename=self._text(root, "iconFilename"),
            map_config=self._get_map_config(root),
            dependencies=self._get_dependencies(root),
        )

        logger.debug(
            "[ModDesc Parser]: Parsed '%s' — %d dependency/dependencies.",
            model.title,
            len(model.dependencies),
        )

        return model

    @staticmethod
    def _text(root: Element, tag: str) -> str | None:
        """
        Get the stripped text of a direct child element, or None.
        :param root: The root of the XML file.
        :param tag: The tag to search for.
        :return: (str) the stripped test if it exists.
        """
        element = root.find(tag)
        return element.text.strip() if element is not None and element.text else None

    def _localised_text(self, root: Element, tag: str) -> str | None:
        """
        Return the 'localised' text of an element that contains multiple language
        tags e.g. en, de, and fr.

        Falls back to None and logs a warning if no English content is found.
        :param root: The root element.
        :param tag: The tag to search for.
        :return: (str) the English localised text.
        """
        element = root.find(tag)
        if element is None:
            return None

        for locale in self._PREFERRED_LOCALES:
            child = element.find(locale)
            if child is not None and child.text:
                return child.text.strip()

        logger.warning(
            "[ModDesc Parser]: No English '%s' found in modDesc.xml.", tag
        )
        return None

    def _get_map_config(self, root: Element) -> MapConfigModel | None:
        """
        Extract config XML filenames from the <maps><map> element.
        :param root: The Root of the XML element.
        :return: A model containing the map configuration data.
        """
        maps_element = root.find("maps")
        if maps_element is None:
            return None

        map_element = maps_element.find("map")
        if map_element is None:
            return None

        return MapConfigModel(
            config_filename=map_element.get("configFilename"),
            vehicles_filename=map_element.get("defaultVehiclesXMLFilename"),
            placeables_filename=map_element.get("defaultPlaceablesXMLFilename"),
            items_filename=map_element.get("defaultItemsXMLFilename"),
            description=self._localised_text(map_element, "description"),
            preview_filename=self._text(map_element, "iconFilename"),
        )

    @staticmethod
    def _get_dependencies(root: Element) -> list[str]:
        """
        Extract a list of required mod dependency IDs.
        :param root: The Root element of the XML file.
        :return: (list) of the map dependencies if they exist.
        """
        dependencies_element = root.find("dependencies")
        if dependencies_element is None:
            return []
        return [
            dep.text.strip()
            for dep in dependencies_element.findall("dependency")
            if dep.text
        ]
