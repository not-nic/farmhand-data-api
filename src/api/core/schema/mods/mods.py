import re
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ModModel(BaseModel):
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

    @field_validator("size")
    def validate_size(cls, value) -> str:
        """
        Validate the size of a ModHub object.
        :param value: the 'float' value of the object
        :return: the size
        """
        match = re.match(r"^(\d+(\.\d+)?)\s*(KB|MB)$", value.strip(), re.IGNORECASE)

        if match:
            size = float(match.group(1))
            unit = match.group(3).upper()

            if unit == "KB":
                return str(size / 1024)
            return str(size)

        raise ValueError(
            f"Invalid size format: {value}. Expected format is '<number> KB' or '<number> MB'."
        )

    @field_validator("platform")
    def validate_platform(cls, value):
        """
        Pydantic Validator to split the platforms a mod is available on into a list
        :param value: the list of platforms as a string
        :return: platforms as a list
        """
        return [platform.strip() for platform in value.split(",")]
