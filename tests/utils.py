"""
Utils for pytest unit tests.
"""

import os
from io import BytesIO
from zipfile import ZipFile

from src.api.core.schema.mods import ModPreviewModel


def load_test_resource(filename: str) -> str:
    """
    Util function to load a file from the resources' folder.
    :param filename: The filename to open.
    :return: The specified resource file.
    """
    filepath = os.path.join("tests", "resources", filename)
    with open(filepath) as file:
        return file.read()


def create_previews_by_category(
    preview_and_category: list[tuple[ModPreviewModel, str]]
) -> dict[str, list[ModPreviewModel]]:
    """
    Groups a list of (category, ModPreviewModel) tuples into a dict by category.

    :param preview_and_category: Tuples of (ModPreviewModel, ModHubMapFilter)
    :return: Dictionary mapping category to list of ModPreviewModel
    """
    grouped = {}

    for model, category in preview_and_category:
        if category not in grouped:
            grouped[category] = []
        grouped[category].append(model)

    return grouped


def create_test_zip_file(file_list: list[str]) -> bytes:
    """
    Create an in-memory zip file used for unit testing.
    :param file_list: The list of files to be in the .zip archive.
    :return: The bytes of the .zip file.
    """
    buffer = BytesIO()
    with ZipFile(buffer, 'w') as zf:
        for file_name in file_list:
            zf.writestr(file_name, "dummy content")
    buffer.seek(0)
    return buffer.read()
