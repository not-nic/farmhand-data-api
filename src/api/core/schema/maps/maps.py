"""
Module containing Map pydantic models.
"""

from datetime import date
from typing import List

from pydantic import BaseModel, field_validator, model_serializer, ConfigDict

from src.api.constants import ModHubMapFilters
from src.api.utils import map_category_to_filter, to_snake_case


class MapModel(BaseModel):
    """
    Pydantic model for a Farming Simulator Map.
    """

    id: int
    name: str
    category: ModHubMapFilters
    author: str
    release_date: date
    version: str

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

    @field_validator("category", mode="before")
    def validate_category(cls, v):
        """
        Convert the category that stored in the databae
        to the ModHub filter.
        :param v: the value to convert.
        :return: the category used in ModHub.
        """
        if isinstance(v, ModHubMapFilters):
            return v
        return map_category_to_filter(v)

    @model_serializer(mode="wrap")
    def serialize_category_as_snake_case(self, handler):
        """
        serialize the category into snake_case.
        :param handler: pydantic handler.
        :return: the category in snake_case.
        """
        data = handler(self)
        data["category"] = to_snake_case(self.category.value)
        return data


class MapsResponse(BaseModel):
    maps: List[MapModel]
    count: int

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)
