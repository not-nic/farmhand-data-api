"""
Abstract base class for the Farming Simulator XML Parsers.

Each implementation of a parser should target a specific Farming Simulator XML
file type e.g. modDesc, maps, vehicles, etc., returning a typed Pydantic Model.
"""

from abc import ABC, abstractmethod
from io import BytesIO
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

    @staticmethod
    def _text(root: Element, tag: str) -> str | None:
        """
        Return the stripped text of a direct child element, or None.

        :param root: The element to search within.
        :param tag: The direct child tag name to find.
        :return: The child's stripped text, or None if not found/empty.
        """
        element = root.find(tag)
        return element.text.strip() if element is not None and element.text else None

    @staticmethod
    def _attr(root: Element, tag: str, attr: str) -> str | None:
        """
        Return a named attribute of a direct child element, or None.

        :param root: The element to search within.
        :param tag: The direct child tag name to find.
        :param attr: The attribute name to read from that child.
        :return: The attribute's value, or None if not found.
        """
        element = root.find(tag)
        return element.get(attr) if element is not None else None

    @abstractmethod
    def parse(self, content: bytes) -> T:
        """
        Parse the target XML file and return a typed Pydantic model.

        :param content: Raw bytes of the XML file to parse.
        :return: Parsed data as a Pydantic model.
        """
        pass
