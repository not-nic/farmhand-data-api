"""
Module containing Enums used within the Farmhand application.
"""

from strenum import StrEnum


class ModHubMapFilters(StrEnum):
    """
    All map filters for the modhub, used to scrape all maps.
    """

    EUROPEAN_MAPS = "mapEurope"
    NORTH_AMERICAN_MAPS = "mapNorthAmerica"
    SOUTH_AMERICAN_MAPS = "mapSouthAmerica"
    OTHER_MAPS = "mapOthers"


class ModHubLabels(StrEnum):
    """
    ModHub mod labels.
    """

    NEW = "NEW!"
    PREFAB = "PREFAB!"
    UPDATE = "UPDATE!"
    UNTAGGED = "untagged"


class FarmhandMapFilters(StrEnum):
    """
    Map filters used internally within the farmhand application.
    """

    EUROPEAN_MAPS = "map_europe"
    NORTH_AMERICAN_MAPS = "map_north_america"
    SOUTH_AMERICAN_MAPS = "map_south_america"
    OTHER_MAPS = "map_others"


class GameVersions(StrEnum):
    """
    Versions of the supported and used for scraping.
    """

    FS_2025 = "fs2025"
    FS_2022 = "fs2022"


class ContentType(StrEnum):
    """
    Content types supported by Farming Simulator save games.
    """

    XML = "application/xml"
    I3D = "application/xml"
    PNG = "image/png"
    JPG = "image/jpeg"
    JPEG = "image/jpeg"
    BINARY_OCTET_STREAM = "binary/octet-stream"


class IngestionStatus(StrEnum):
    """
    Ingestion Status Enums for map processing.

    Steps:
        - Pending: The Mod has been scraped from the ModHub.
        - Downloaded: The mod has been downloaded and stored in the S3/MinIO bucket.
        - Extracted: The required files have been extracted from the bucket, stored in S3,
                     and the archive deleted.
        - Parsed: The files are parsed, and the database updated with ModDesc, XML Data, etc.
        - Complete: The mod is ingested.
        - Failed: it failed on one of these steps and needs to be retried.
    """

    PENDING = "pending"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    PARSING = "parsing"
    PARSED = "parsed"
    COMPLETE = "complete"
    FAILED = "failed"
