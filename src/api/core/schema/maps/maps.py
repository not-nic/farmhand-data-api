"""
Module containing Map pydantic models.
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from src.api.constants import FarmhandMapFilters


class MapModel(BaseModel):
    """
    Pydantic model for a Farming Simulator Map.
    """

    id: int
    name: str
    category: FarmhandMapFilters
    author: str
    release_date: date
    version: str
    zip_filename: str
    data_uri: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

    @field_validator("category", mode="before")
    def validate_category(cls, value):
        """
        Convert a Farming Simulator category name into a snake_case map filter name.
        For example, 'European Maps' -> 'map_europe'.

        :param value: The category to convert.
        :return: A snake_case formatted filter string.
        :raises: ValueError if category is not recognised.
        """

        if isinstance(value, FarmhandMapFilters) or value in FarmhandMapFilters:
            return value
        else:
            mapping = {
                "European Maps": FarmhandMapFilters.EUROPEAN_MAPS,
                "North American Maps": FarmhandMapFilters.NORTH_AMERICAN_MAPS,
                "South American Maps": FarmhandMapFilters.SOUTH_AMERICAN_MAPS,
                "Other/Fantasy Maps": FarmhandMapFilters.OTHER_MAPS
            }

            try:
                return mapping[value]
            except KeyError:
                raise ValueError(
                    f"Invalid category: '{value}', "
                    f"Valid categories are: {[f.value for f in FarmhandMapFilters]}"
                )


class MapResponse(BaseModel):
    """
    Pydantic model for the map response object.
    """
    id: int
    name: str
    category: FarmhandMapFilters
    author: str
    release_date: date
    version: str


class MapsResponse(BaseModel):
    """
    Pydantic model response object containing multiple maps.
    """
    maps: list[MapResponse]
    count: int

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class MapUploadResponse(BaseModel):
    """
    Pydantic model for pre-signed URL response.
    """
    id: int
    url: str
