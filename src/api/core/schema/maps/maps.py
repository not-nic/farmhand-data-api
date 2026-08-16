"""
Module containing Map pydantic models.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict, field_validator

from src.api.constants import FarmhandMapFilters
from src.api.core.db.models import Map
from src.api.core.schema.assets import AssetResponse
from src.api.core.schema.maps.farmlands import FarmlandResponse
from src.api.core.schema.mods.mod_desc import (
    ChangeLogResponse,
    DependencyResponse,
)


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
    data_uri: str | None = None

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
                "Other/Fantasy Maps": FarmhandMapFilters.OTHER_MAPS,
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
    description: str | None = None
    tagline: str | None = None
    dependencies: list[DependencyResponse] = []
    assets: list[AssetResponse] = []
    changelogs: list[ChangeLogResponse] = []
    farmlands: list[FarmlandResponse] = []
    width: int | None = None
    height: int | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def from_map(cls, map_obj: Map) -> MapResponse:
        """
        Create a pydantic model from a map database object.
        :param map_obj: A given map database object.
        :return: A re-structured map pydantic model.
        """
        description: str | None = map_obj.mod_description.description if map_obj.mod_description else None
        tagline: str | None = map_obj.mod_description.tagline if map_obj.mod_description else None
        width: int | None = map_obj.information.width if map_obj.information else None
        height: int | None = map_obj.information.height if map_obj.information else None

        dependencies: list[DependencyResponse] = [
            DependencyResponse.model_validate(d) for d in map_obj.dependencies
        ]
        assets: list[AssetResponse] = [AssetResponse.model_validate(a) for a in map_obj.assets]
        changelogs: list[ChangeLogResponse] = [
            ChangeLogResponse.model_validate(c) for c in map_obj.changelogs
        ]
        farmlands: list[FarmlandResponse] = [
            FarmlandResponse.model_validate(f) for f in map_obj.farmlands
        ]

        return cls(
            id=map_obj.id,
            name=map_obj.name,
            category=FarmhandMapFilters(map_obj.category),
            author=map_obj.author,
            release_date=map_obj.release_date,
            version=map_obj.version,
            description=description,
            tagline=tagline,
            dependencies=dependencies,
            assets=assets,
            changelogs=changelogs,
            farmlands=farmlands,
            width=width,
            height=height,
        )


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


class MapInformationResponse(BaseModel):
    """
    Pydantic response model for a map's parsed maps.xml information.
    """

    width: int | None = None
    height: int | None = None

    model_config = ConfigDict(from_attributes=True)
