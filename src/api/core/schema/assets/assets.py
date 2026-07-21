"""
Module containing Asset pydantic models.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.api.constants import AssetType


class AssetResponse(BaseModel):
    """
    Pydantic model for an 'asset' .json object within a 'mod' response.
    """
    asset_type: AssetType
    uri: str = Field(alias="asset_uri")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ResolvedAssetResponse(BaseModel):
    """
    Pydantic model for a resolved asset includes the pre-signed URL
    and expiry time.
    """
    url: str
    expires_at: datetime
