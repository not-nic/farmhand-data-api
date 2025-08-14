from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from src.api.constants import ModHubLabels


class ModDetailModel(BaseModel):
    """
    Pydantic model for a Farming Simulator Mod Hub mod.
    """

    id: int
    name: str
    game: str = Field(..., alias="Game")
    manufacturer: str = Field(..., alias="Manufacturer")
    category: str = Field(..., alias="Category")
    author: str = Field(..., alias="Author")
    size: str = Field(..., alias="Size")
    version: str = Field(..., alias="Version")
    release_date: Optional[date | str] = Field(..., alias="Released")
    file_url: str
    zip_filename: str
    platform: Optional[list | str] = Field(..., alias="Platform")

    @field_validator("release_date")
    def validate_release_date(cls, value):
        """
        Pydantic Validator to validate the release date of a mod into a date object.
        :param value: (str) of a date
        :return: (date) object of the incoming date
        """
        if isinstance(value, str):
            try:
                return datetime.strptime(value, "%d.%m.%Y").date()
            except ValueError:
                raise ValueError(f"Invalid date format: {value}. Expected format is 'dd.mm.yyyy'.")
        return value

    @field_validator("platform")
    def validate_platform(cls, value):
        """
        Pydantic Validator to split the platforms a mod is available on into a list
        :param value: the list of platforms as a string
        :return: platforms as a list
        """
        return [platform.strip() for platform in value.split(",")]


class ModPreviewModel(BaseModel):
    """
    Pydantic Model for a mod preview found on the 'mods' pages.
    """
    id: int
    name: str
    label: ModHubLabels
