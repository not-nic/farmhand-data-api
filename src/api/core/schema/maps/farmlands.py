"""
Pydantic models for a parsed farmlands.xml file.
"""

from pydantic import BaseModel, Field, ConfigDict

from src.api.constants import SoilType


class FarmlandXmlEntryModel(BaseModel):
    """
    A single <farmland> entry from farmlands.xml.
    """

    farmland_number: int
    price_scale: float = 1.0
    default: bool = False


class FarmlandsXmlModel(BaseModel):
    """
    Parsed representation of a map's farmlands.xml file.
    """

    price_per_ha: float | None = None
    farmlands: list[FarmlandXmlEntryModel] = Field(default_factory=list)


class SoilTypeResponse(BaseModel):
    """
    Pydantic response model for a farmland's soil type composition.
    """

    soil_type: SoilType
    percentage: float

    model_config = ConfigDict(from_attributes=True)


class FarmlandResponse(BaseModel):
    """
    Pydantic response model for a single farmland.
    """

    number: int
    price_per_ha: float | None = None
    price_scale: float | None = None
    default: bool = False
    size_ha: float | None = None
    coordinates: list | None = None
    soil_types: list[SoilTypeResponse] = []

    model_config = ConfigDict(from_attributes=True)


class FarmlandRescaleRequest(BaseModel):
    """
    Pydantic Model for a Farmland rescale request.
    """

    offset_x: float
    offset_y: float
    scale_x: float = Field(default=1.0, gt=0)
    scale_y: float = Field(default=1.0, gt=0)
