"""
Pydantic models for a parsed .i3d file.
"""

from pydantic import BaseModel, Field


class InfoLayerOptionModel(BaseModel):
    """
    A single value/name Option entry within an InfoLayer Group.
    """

    value: int
    name: str


class InfoLayerGroupModel(BaseModel):
    """
    A single Group within an InfoLayer. InfoLayers can pack multiple
    Groups into different bit ranges of the same pixel value — decode
    a raw value against a specific group using first_channel/num_channels
    rather than treating the value as a direct Option lookup.
    """

    name: str
    first_channel: int
    num_channels: int
    options: list[InfoLayerOptionModel] = Field(default_factory=list)

    def decode(self, raw_value: int) -> int:
        """
        Extract this group's bits from a raw multi-channel pixel value.
        :param raw_value: The full raw pixel value from the GRLE.
        :return: This group's own value, isolated from any other groups
            packed into the same pixel.
        """
        mask = (1 << self.num_channels) - 1
        return (raw_value >> self.first_channel) & mask


class InfoLayerModel(BaseModel):
    """
    A single info layer discovered in a map's map.i3d file.
    """

    layer_key: str
    i3d_file_id: str | None = None
    grle_filename: str | None = None
    groups: list[InfoLayerGroupModel] = Field(default_factory=list)


class I3dModel(BaseModel):
    """
    Aggregated result of parsing an .i3d file. Generic across entity
    types (maps, vehicles, placeables) — new extraction methods add
    their own field here as they're built.
    """

    info_layers: list[InfoLayerModel] = Field(default_factory=list)
