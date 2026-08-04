"""
Python module containing validation functions used within the Schemas.
"""

from collections.abc import Callable
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

    @staticmethod
    def to_list[T](value: str | list[T] | None, cast: Callable[[str], T]) -> list[T]:
        """
        Split a space-separated attribute into a list, converting each item.

        E.g. to_list('301 331 361', int) -> [301, 331, 361]
             to_list('0.8 1.0 1.25', float) -> [0.8, 1.0, 1.25]
             to_list('RYE MUSTARD SPELT') -> ['RYE', 'MUSTARD', 'SPELT']
        """
        if value is None:
            return []
        items = value.split() if isinstance(value, str) else value
        return [cast(v) for v in items]


Filename = Annotated[str | None, BeforeValidator(Validators.strip_directory)]
DDSFilename = Annotated[str | None, BeforeValidator(Validators.as_dds_filename)]
