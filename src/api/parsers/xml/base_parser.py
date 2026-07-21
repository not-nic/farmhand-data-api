"""
Abstract base class for the Farming Simulator XML Parsers.

Each implementation of a parser should target a specific Farming Simulator XML
file type e.g. modDesc, maps, vehicles, etc., returning a typed Pydantic Model.
"""

from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path
from xml.etree.ElementTree import Element, ParseError
from xml.etree.ElementTree import parse as parse_xml

from src.api.core.logger import logger


class BaseXmlParser[T](ABC):
    """
    Abstract base for Farming Simulator XML file parsers.

    Subclasses implement `parse` to extract data from a specific XML
    file type and return a typed Pydantic model.
    """

    @staticmethod
    def _load(content: bytes) -> Element:
        """
        Parse an XML file and return its root element.

        :param content: (bytes) The content of the XML file.
        :return: The root Element of the parsed XML tree.
        :raises ParseError: If the file is not valid XML.
        """
        try:
            return parse_xml(BytesIO(content)).getroot()
        except ParseError as exc:
            logger.error("[XML Parser]: Failed to parse XML content: %s", exc)
            raise

    @abstractmethod
    def parse(self, file_path: Path) -> T:
        """
        Parse the target XML file and return a typed Pydantic model.

        :param file_path: Path to the XML file to parse.
        :return: Parsed data as a Pydantic model.
        """
        pass
