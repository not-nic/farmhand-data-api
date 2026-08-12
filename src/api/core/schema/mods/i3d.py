"""
Pydantic models for a parsed .i3d file.
"""

from pydantic import BaseModel, Field


class InfoLayerOptionModel(BaseModel):
    """
    A Model containing a value/name Option entry for an InfoLayer Group.
    """

    value: int
    name: str


class InfoLayerGroupModel(BaseModel):
    """
    Pydantic model for an InfoLayer Group. InfoLayers can pack multiple
    groups into different bit ranges of the same pixel value.
    """

    name: str
    first_channel: int
    num_channels: int
    options: list[InfoLayerOptionModel] = Field(default_factory=list)

    def decode(self, raw_value: int) -> int:
        """
        Extract this group's bits from a raw multichannel pixel value.

        :param raw_value: (int) The full raw pixel value from the GRLE.
        :return: (int) This group's own value packed into the same pixel.
        """
        mask = (1 << self.num_channels) - 1
        return (raw_value >> self.first_channel) & mask


class InfoLayerModel(BaseModel):
    """
    Pydantic model representing a layer model from a map.i3d.
    """

    layer_key: str
    i3d_file_id: str | None = None
    grle_filename: str | None = None
    groups: list[InfoLayerGroupModel] = Field(default_factory=list)


class I3dModel(BaseModel):
    """
    Pydantic model representing an map.i3d file.
    """

    info_layers: list[InfoLayerModel] = Field(default_factory=list)
