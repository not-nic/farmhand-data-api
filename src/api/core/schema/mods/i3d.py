"""
Python module containing pydantic models for a .i3d XML file.
"""

from pydantic import BaseModel, Field


class InfoLayerOptionModel(BaseModel):
    """
    A single value/name Option entry nested under an InfoLayer's Group(s).
    """

    value: int
    name: str


class InfoLayerModel(BaseModel):
    """
    A single info layer discovered in a map's map.i3d file.
    """

    layer_key: str
    i3d_file_id: str | None = None
    grle_filename: str | None = None
    options: list[InfoLayerOptionModel] = Field(default_factory=list)


class I3dModel(BaseModel):
    """
    Pydantic model of a i3d file.
    """

    info_layers: list[InfoLayerModel] = Field(default_factory=list)

