"""
Pydantic model for an item parsed from a Farming Simulator storeItems XML file.
"""

from pydantic import BaseModel, Field


class StoreItemModel(BaseModel):
    """
    A single base game or DLC vehicle entry from storeItems_en.xml.

    Attributes:
        config_path: Canonical vehicle key, see utils.normalise_config_path.
        name: Resolved display name.
        brand: Display brand.
        category: Raw shop category, e.g. "TRACTORSM".
        price: The in-game price.
        dlc: The DLC title, or None for the base game.
        functions: Store description lines.
    """

    config_path: str
    name: str
    brand: str | None = None
    category: str | None = None
    price: int = 0
    dlc: str | None = None
    functions: list[str] = Field(default_factory=list)
