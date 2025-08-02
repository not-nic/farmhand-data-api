"""
Farmhand util functions.
"""

from typing import Union

from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from src.api.constants import ContentType


def format_pydantic_errors(
        validation_error: Union[ValidationError | RequestValidationError],
) -> dict:
    """
    Util function to nicely format pydantic validation errors.
    :param validation_error: Pydantic ValidationError
    :return: (dict) error message 'detail' response
    """
    errors = validation_error.errors()
    if errors:
        messages = [err.get("msg", "Validation error") for err in errors]
        return {"detail": "; ".join(messages)}
    return {"detail": "Unknown validation error"}


def parse_version(v: str) -> list:
    """
    Parse the version of a mod and split it on each part.
    :param v: (str) mod version
    :return: a list of the integer parts.
    """
    return [int(part) for part in v.split(".")]


def format_file_size(file_size_bytes: int) -> str:
    """
    Converts a file size bytes response into a human-readable string (e.g. KB, MB, GB).
    :param file_size_bytes: File size in bytes.
    :return: Human-readable file size string.
    """
    if file_size_bytes == 0:
        return "0 bytes"

    size_name = ("bytes", "KB", "MB", "GB", "TB")
    i = 0
    double_size = float(file_size_bytes)

    while double_size >= 1024 and i < len(size_name) - 1:
        double_size /= 1024
        i += 1

    return f"{double_size:.2f} {size_name[i]}"


def get_filename_from_url(file_url: str) -> str:
    """
    Function to get the '.zip' filename from a Giants CDN url.
    :param file_url: the giants CDN url.
    :return: string of the .zip filename.
    """
    return file_url.split("/")[-1]


def extension_to_content_type(extension: str) -> str:
    """
    Converts a file extension into its respective content type.
    :param extension: The file extension (".xml", ".i3d" ".png", ".jpeg")
    :return: The corresponding MIME content type string.
    """
    normalized_ext = extension.lower().lstrip(".")
    try:
        return ContentType[normalized_ext.upper()].value
    except KeyError:
        return ContentType.BINARY_OCTET_STREAM.value
