"""
Parser for Farming Simulator l10n XML files (e.g. l10n_en.xml), used to give
fill types and shop categories their in-game display text.
"""

from src.api.constants import VehicleCategory
from src.api.parsers.xml.base_parser import BaseXmlParser
from src.api.utils import label_from_key

_L10N_PREFIX = "$l10n_"


class L10n:
    """
    Case-insensitive lookup of l10n texts, falling back to a key-derived label.
    """

    def __init__(self, texts: dict[str, str] | None = None) -> None:
        """
        :param texts: l10n texts keyed by lower-cased key.
        """
        self.texts = texts or {}

    def text(self, key: str) -> str | None:
        """
        :param key: A bare key ("fillType_diesel") or reference ("$l10n_fillType_diesel").
        :return: The display text, or None if the key is unknown.
        """
        return self.texts.get(key.removeprefix(_L10N_PREFIX).lower())

    def fill_type(self, key: str) -> str:
        """
        :param key: A fill type name, e.g. "ELECTRICCHARGE".
        :return: E.g. "Electric Charge".
        """
        return self.text(f"fillType_{key}") or label_from_key(key)

    def category(self, key: str) -> str:
        """
        Prefers the curated label, then the l10n text, then a key-derived label.
        :param key: A shop category name, e.g. "TRACTORSM".
        :return: E.g. "Medium Tractors".
        """
        category = VehicleCategory.from_key(key)
        return (
            (category and category.value)
            or self.text(f"category_{key}")
            or label_from_key(key)
        )


class L10nXmlParser(BaseXmlParser[L10n]):
    """
    Parses an l10n XML file into an L10n lookup.

    Supports the FS22/25 format (<l10n><elements><e k="" v=""/>) and the
    older format (<l10n><texts><text name="" text=""/>).
    """

    def parse(self, content: bytes) -> L10n:
        """
        :param content: Raw bytes of the l10n XML file.
        :return: An L10n lookup.
        :raises ParseError: If the content is not valid XML.
        """
        root = self._load(content)
        texts: dict[str, str] = {}
        for element in root.iter("e"):
            if (key := element.get("k")) and (value := element.get("v")) is not None:
                texts[key.lower()] = value
        for element in root.iter("text"):
            if (key := element.get("name")) and (value := element.get("text")) is not None:
                texts[key.lower()] = value
        return L10n(texts)
