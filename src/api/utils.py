"""
Farmhand util functions.
"""
import re
from datetime import datetime, timedelta

from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from src.api.constants import ContentType, IngestionStatus
from src.api.core.db.models import Map


def format_pydantic_errors(
    validation_error: ValidationError | RequestValidationError,
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


def is_newer_version(current_version: str, new_version: str) -> bool:
    """
    Compare two version strings like '1.0.0.0'.
    Return True if new_version is greater.
    :param new_version: The new map version from ModHub.
    :param current_version: The current map version in the db
    """
    return parse_version(new_version) > parse_version(current_version)


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
    Function to get the '.zip' filename from a 'Giants' CDN url.
    :param file_url: The giants CDN url.
    :return: String of the .zip filename.
    """
    return file_url.split("/")[-1]


def key_from_s3_uri(uri: str) -> str:
    """
    Extract the object key from a full S3 URI.
    :param uri: S3 URI e.g. 's3://farmhand-assets/123/assets/icon.png'.
    :return: The object key, e.g. '123/assets/icon.png'.
    """
    return uri.split("/", 3)[-1].strip().strip('"')


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


def is_past_retry_cooldown(map_obj: Map, cooldown_minutes: int) -> bool:
    """
    Check if a FAILED map's retry cooldown has elapsed. Maps that
    aren't FAILED are always considered past cooldown.

    :param map_obj: The map to check.
    :param cooldown_minutes: Minutes to wait before retrying a FAILED map.
    :return: True if the map isn't FAILED, or its cooldown has elapsed.
    """
    if map_obj.ingestion_status != IngestionStatus.FAILED:
        return True

    cooldown_elapsed = datetime.now() - timedelta(minutes=cooldown_minutes)
    return map_obj.ingestion_updated_at < cooldown_elapsed


def normalise_config_path(path: str) -> str | None:
    """
    Normalise a Farming Simulator config path into a canonical vehicle key.

    Base game paths ("data/vehicles/...", "$data/vehicles/...", "vehicles/...") become
    "vehicles/...", and DLC paths (absolute ".../pdlc/<pack>/vehicles/..." or
    "$pdlcdir$<pack>/vehicles/...") become "pdlc/<pack>/vehicles/...".

    Mod content ("$moddir$", "$mapdir$", "/mods/") and anything not under a
    "vehicles/" segment is out of scope.

    :param path: A given path, e.g. "$data/vehicles/fendt/vario700/vario700.xml".
    :return: The canonical key, e.g. "vehicles/fendt/vario700/vario700.xml", or None if out of scope.
    """
    path = path.strip().replace("\\", "/")
    if path.startswith(("$moddir$", "$mapdir$")) or "/mods/" in path.lower():
        return None

    if path.startswith("$pdlcdir$"):
        dlc_path = path.removeprefix("$pdlcdir$")
    elif "/pdlc/" in path:
        dlc_path = path.split("/pdlc/", 1)[1]
    else:
        dlc_path = None

    if dlc_path is not None:
        segments = dlc_path.split("/")
        if len(segments) > 2 and segments[1] == "vehicles":
            return f"pdlc/{dlc_path}"
        return None

    for prefix in ("$data/", "data/"):
        if path.startswith(prefix):
            path = path.removeprefix(prefix)
            break
    return path if path.startswith("vehicles/") else None


def label_from_key(value: str) -> str:
    """
    Turn a raw Farming Simulator key into readable text, used when no l10n text exists.

    E.g. "teleHandler" -> "Tele Handler", "GRASS_WINDROW" -> "Grass Windrow".

    :param value: A camelCase, snake_case or upper-case key.
    :return: The key split into title-cased words.
    """
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value).replace("_", " ").split()
    return " ".join(word.capitalize() for word in words)


def display_name(brand: str | None, name: str) -> str:
    """
    Prefix a name with its brand, as the in-game shop does for owned vehicles.

    :param brand: The display brand, e.g. "Fendt".
    :param name: The vehicle or motor name, e.g. "728 Vario".
    :return: E.g. "Fendt 728 Vario", without repeating a brand the name already starts with.
    """
    if not brand or name.lower().startswith(brand.lower()):
        return name
    return f"{brand} {name}"


def strip_dlc_prefix(path: str) -> str:
    """
    Drop the "pdlc/<pack>/" prefix of a canonical DLC path, giving its path inside an
    archive that stores DLC content alongside the base game under "vehicles/".

    :param path: E.g. "pdlc/skyAgriculturePack/vehicles/skyAgriculture/hr3000_30/hr3000_30.xml".
    :return: E.g. "vehicles/skyAgriculture/hr3000_30/hr3000_30.xml", or the path unchanged.
    """
    if path.startswith("pdlc/"):
        return path.split("/", 2)[2] if path.count("/") >= 2 else path
    return path
