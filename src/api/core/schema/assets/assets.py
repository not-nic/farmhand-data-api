"""
Module containing Asset pydantic models.
"""

from pydantic import BaseModel, ConfigDict, Field

from src.api.constants import AssetType


class AssetResponse(BaseModel):
    asset_type: AssetType
    uri: str = Field(alias="asset_uri")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
