"""
Python module containing validation functions used within the Schemas.
"""

from typing import Annotated

from pydantic import BeforeValidator


class Validators:
    """
    Class containing generic Pydantic validator functions.
    """

    @staticmethod
    def strip_directory(value: str | None) -> str | None:
        """
        Return just the filename from a modDesc path.

        E.g. 'maps/config/vehicles.xml' -> 'vehicles.xml'
        """
        if value is None:
            return None
        return value.split("/")[-1]

    @staticmethod
    def as_dds_filename(value: str | None) -> str | None:
        """
        Return just the filename, with the extension forced to .dds.

        modDesc.xml often lists images as .png, but the file extracted
        into the bucket is always .dds.

        E.g. 'icons/preview.png' -> 'preview.dds'
        """
        if value is None:
            return None
        stem = value.split("/")[-1].rsplit(".", 1)[0]
        return f"{stem}.dds"


Filename = Annotated[str | None, BeforeValidator(Validators.strip_directory)]
DDSFilename = Annotated[str | None, BeforeValidator(Validators.as_dds_filename)]
