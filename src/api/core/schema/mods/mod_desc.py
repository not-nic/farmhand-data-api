"""
Pydantic models related to the modDesc.xml file used within a Farming Simulator
Mod.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MapConfigModel(BaseModel):
    """
    XML filenames extracted from the <map> element in modDesc.xml.

    Only the filenames are stored — the full S3 path is constructed by
    the service layer using the map's known restructured directory layout
    (all config XML files live under config/).
    """

    config_filename: str | None = None
    vehicles_filename: str | None = None
    placeables_filename: str | None = None
    items_filename: str | None = None
    description: str | None = None
    preview_filename: str | None = None

    @field_validator(
        "config_filename",
        "vehicles_filename",
        "placeables_filename",
        "items_filename",
        "preview_filename",
        mode="before",
    )
    @classmethod
    def extract_filename(cls, value: str | None) -> str | None:
        """
        Strip any directory prefix from the modDesc path and return just
        the filename.

        E.g. 'maps/config/vehicles.xml' -> 'vehicles.xml'
        """
        if value is None:
            return None
        return value.split("/")[-1]


class ModDescModel(BaseModel):
    """
    Parsed representation of a Farming Simulator modDesc.xml file.

    Keeps only what is useful to the farmhand pipeline and not already
    sourced from ModHub scraping (author, version, name are excluded).
    """

    title: str | None = None
    description: str | None = None
    icon_filename: str | None = None
    map_config: MapConfigModel | None = None
    dependencies: list[str] = Field(default_factory=list)

    @field_validator("icon_filename", mode="before")
    @classmethod
    def extract_filename(cls, value: str | None) -> str | None:
        """
        Strip any directory prefix from the modDesc path and return just
        the filename.

        E.g. 'icons/icon_FS25_Le_Mechet.png' -> 'icon_FS25_Le_Mechet.png'
        """
        if value is None:
            return None
        return value.split("/")[-1]


class DependencyResponse(BaseModel):
    """
    Pydantic response model for map dependencies.
    """
    mod_id: str
    model_config = ConfigDict(from_attributes=True)


class ModDescriptionResponse(BaseModel):
    """
    Pydantic response model for a mod_description.
    """

    description: str | None = None
    map_description: str | None = None

    model_config = ConfigDict(from_attributes=True)

