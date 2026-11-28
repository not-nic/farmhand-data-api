"""
Parser for Farming Simulator storeItems XML files (e.g. storeItems_en.xml).
"""

from src.api.core.schema.vehicles.store_items import StoreItemModel
from src.api.parsers.xml.base_parser import BaseXmlParser
from src.api.utils import normalise_config_path


class StoreItemsXmlParser(BaseXmlParser[list[StoreItemModel]]):
    """
    Parses a storeItems XML file into a list of StoreItemModel, keeping only
    vehicles that are part of the base game or a DLC.
    """

    def parse(self, content: bytes) -> list[StoreItemModel]:
        """
        Parse storeItems XML bytes and return the in-scope vehicle items.

        Items flagged as mods, and items that are not vehicles (placeables, animals, etc.),
        are dropped.

        :param content: Raw bytes of the storeItems XML file.
        :return: List of parsed StoreItemModel.
        :raises ParseError: If the content is not valid XML.
        """
        root = self._load(content)
        items: list[StoreItemModel] = []

        for item in root.findall("item"):
            if item.get("isMod", "false").lower() == "true":
                continue

            config_path = normalise_config_path(item.get("xmlFilename", ""))
            if config_path is None:
                continue

            items.append(
                StoreItemModel(
                    config_path=config_path,
                    name=item.get("name", ""),
                    brand=item.get("brand") or None,
                    category=item.get("category") or None,
                    price=int(float(item.get("price") or 0)),
                    dlc=item.get("dlcTitle") or None,
                    functions=[
                        f.text.strip() for f in item.findall("function") if f.text and f.text.strip()
                    ],
                )
            )

        return items
