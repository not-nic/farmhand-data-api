"""
Pydantic models related to the modDesc.xml file used within a Farming Simulator
Mod.
"""

from pydantic import BaseModel, ConfigDict, Field

from src.api.core.schema.validators import DDSFilename, Filename


class ChangeLogModel(BaseModel):
    """
    A single versioned changelog entry extracted from a map's description text.
    """

    version: str
    notes: list[str] = Field(default_factory=list)
    requires_new_savegame: bool | None = None


class MapConfigModel(BaseModel):
    """
    XML filenames extracted from the <map> element in modDesc.xml.

    Only the filenames are stored — the full S3 path is constructed by
    the service layer using the map's known restructured directory layout
    (all config XML files live under config/, image assets under assets/).
    """

    config_filename: Filename = None
    vehicles_filename: Filename = None
    placeables_filename: Filename = None
    items_filename: Filename = None
    description: str | None = None
    preview_filename: DDSFilename = None


class ModDescModel(BaseModel):
    """
    Parsed representation of a Farming Simulator modDesc.xml file.

    Keeps only what is useful to the farmhand pipeline and not already
    sourced from ModHub scraping (author, version, name are excluded).
    """

    title: str | None = None
    description: str | None = None
    changelogs: list[ChangeLogModel] = Field(default_factory=list)
    icon_filename: DDSFilename = None
    map_config: MapConfigModel | None = None
    dependencies: list[str] = Field(default_factory=list)


class DependencyResponse(BaseModel):
    """
    Pydantic response model for map dependencies.
    """
    mod_id: str
    model_config = ConfigDict(from_attributes=True)


class ChangeLogResponse(BaseModel):
    """
    Pydantic response model for a single map changelog entry.
    """

    version: str
    notes: list[str]
    requires_new_savegame: bool | None = None

    model_config = ConfigDict(from_attributes=True)


class ModDescriptionResponse(BaseModel):
    """
    Pydantic response model for a mod_description.
    """

    description: str | None = None
    map_description: str | None = None

    model_config = ConfigDict(from_attributes=True)

