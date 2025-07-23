"""
Collection of Enums used within the Farmhand service.
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


class GameVersions(StrEnum):
    """
    Versions of the supported and used for scraping.
    """

    FS_2025 = "fs2025"
    FS_2022 = "fs2022"
