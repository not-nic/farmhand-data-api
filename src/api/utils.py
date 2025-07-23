"""
Farmhand util functions.
"""

from typing import Union

from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from src.api.constants import ModHubMapFilters


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


def map_category_to_filter(category: str) -> ModHubMapFilters:
    """
    Map a 'Rich text' farming simulator category to its equivalent map
    filter.
    :param category: the category to convert.
    :return: the mapFilter equivalent.
    :raises: ValueError if category is not recognised.
    """
    mapping = {
        "European Maps": ModHubMapFilters.EUROPEAN_MAPS,
        "North American Maps": ModHubMapFilters.NORTH_AMERICAN_MAPS,
        "South American Maps": ModHubMapFilters.SOUTH_AMERICAN_MAPS,
        "Other/Fantasy Maps": ModHubMapFilters.OTHER_MAPS,
    }

    try:
        return mapping[category]
    except KeyError:
        raise ValueError(f"Unrecognised category: {category}")


def to_snake_case(value: str) -> str:
    """
    Convert a camelCase string into snake_case.
    :param value: the value to convert.
    :return: the value in snake_case.
    """
    result = []
    for index, char in enumerate(value):
        if char.isupper() and index != 0:
            result.append("_")
        result.append(char.lower())
    return "".join(result)
