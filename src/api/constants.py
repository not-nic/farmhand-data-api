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
    WEBP = "image/webp"
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


class XmlHandler(StrEnum):
    """
    The XML handlers that run as part of the 'EXTRACTED' parse stage, in
    the order they're registered in MapXmlParserService. Used to select a
    subset of handlers to re-run on a reingest, e.g. just 'vehicles'.
    """

    MOD_DESC = "mod_desc"
    VEHICLES = "vehicles"
    MAPS = "maps"
    INFO_LAYERS = "info_layers"
    FARMLANDS = "farmlands"


class AssetType(StrEnum):
    """
    Assets used in a farming simulator Mod,
    e.g. Icon, Overview and Preview .dds.

    Map assets:
        ICON - mod icon from modDesc.xml iconFilename.
        OVERVIEW - top-down map overview image from maps.xml.
        PREVIEW - map preview/thumbnail image.
    """
    ICON = "icon"
    OVERVIEW = "overview"
    PREVIEW = "preview"


class SoilType(StrEnum):
    """
    Precision Farming soil type classification.
    """

    LOAMY_SAND = "loamy_sand"
    SANDY_LOAM = "sandy_loam"
    LOAM = "loam"
    SILTY_CLAY = "silty_clay"


class AreaType(StrEnum):
    """
    Area Type Enum used within a map.i3d file to split farmlands from unusable areas.
    """
    FARMLAND = "Open Land"
    CITY = "City"
    VILLAGE = "Village"
    HARBOR = "Harbor"
    INDUSTRIAL = "Industrial"
    OPEN_WATER = "Open Water"
    NO_WATER = "No Water"
    NEAR_WATER = "Near Water"
    UNKNOWN = "Unknown"


class IgnoredFillType(StrEnum):
    """
    Fill types that are internal to the game and never shown, e.g. brake air.
    """

    AIR = "AIR"


class VehicleCategory(StrEnum):
    """
    Vehicle shop categories Enum.
    """

    ANIMALTRANSPORT = "Animal Transport"
    AUGERWAGONS = "Auger Wagons"
    BALELOADERS = "Bale Loaders"
    BALERSROUND = "Round Balers"
    BALERSSQUARE = "Square Balers"
    BALEWRAPPERS = "Bale Wrappers"
    BALINGMISC = "Baling Equipment"
    BANANACULTIVATION = "Banana Equipment"
    BARRELS = "Barrels"
    BEETHARVESTERCUTTERS = "Beet Harvester Headers"
    BEETHARVESTERS = "Beet Harvesters"
    BEETLOADING = "Beet Loaders"
    BELTS = "Conveyor Belts"
    CARS = "Cars"
    COFFEECULTIVATION = "Coffee Equipment"
    COMBINEWINDROWER = "Swathers"
    CORNHEADERS = "Corn Headers"
    COTTONHARVESTERS = "Cotton Harvesters"
    COTTONTRANSPORT = "Cotton Transport"
    CULTIVATORS = "Cultivators"
    CUTTERS = "Headers"
    CUTTERTRAILERS = "Header Trailers"
    DISCHARROWS = "Disc Harrows"
    FERTILIZERSPREADERS = "Fertilizer Spreaders"
    FORAGEHARVESTERCUTTERS = "Forage Harvester Headers"
    FORAGEHARVESTERCUTTERTRAILERS = "Forage Harvester Header Trailers"
    FORAGEHARVESTERS = "Forage Harvesters"
    FORAGEMIXERS = "Forage Mixers"
    FORESTRYEXCAVATORS = "Forestry Excavators"
    FORESTRYEXCAVATORTOOLS = "Forestry Excavator Tools"
    FORESTRYFORWARDERS = "Forwarders"
    FORESTRYHARVESTERS = "Forestry Harvesters"
    FORESTRYMISC = "Forestry Equipment"
    FORESTRYMULCHERS = "Forestry Mulchers"
    FORESTRYPLANTERS = "Tree Planters"
    FORESTRYSTUMPCUTTERS = "Stump Cutters"
    FORESTRYWINCHES = "Forestry Winches"
    FORKLIFTS = "Forklifts"
    FRONTLOADERS = "Front Loaders"
    FRONTLOADERTOOLS = "Front Loader Tools"
    FRONTLOADERVEHICLES = "Front Loader Vehicles"
    GRAPEHARVESTERS = "Grape Harvesters"
    GRAPETOOLS = "Grape Tools"
    GRAPETRAILERS = "Grape Trailers"
    GRASSLANDCARE = "Grassland Care"
    GREENBEANHARVESTERS = "Green Bean Harvesters"
    HANDTOOLSMISC = "Hand Tools"
    HARVESTERS = "Harvesters"
    LEVELER = "Levelers"
    LOADERWAGONS = "Loader Wagons"
    LOWLOADERS = "Low Loaders"
    MANURESPREADERS = "Manure Spreaders"
    MISC = "Miscellaneous"
    MISCDRIVABLES = "Miscellaneous Vehicles"
    MOWERS = "Mowers"
    MULCHERS = "Mulchers"
    NEXAT = "NEXAT"
    OLIVEHARVESTERS = "Olive Harvesters"
    ONIONHARVESTING = "Onion Harvesters"
    ONIONPLANTING = "Onion Planters"
    PEAHARVESTERS = "Pea Harvesters"
    PLANTERS = "Planters"
    PLOWS = "Plows"
    POTATOHARVESTING = "Potato Harvesters"
    POTATOPLANTING = "Potato Planters"
    POWERHARROWS = "Power Harrows"
    RICEHARVESTERS = "Rice Harvesters"
    RICEPLANTERS = "Rice Planters"
    ROLLERS = "Rollers"
    SEEDERS = "Seeders"
    SEEDTANKS = "Seed Tanks"
    SILOCOMPACTION = "Silo Compaction"
    SKIDSTEERTOOLS = "Skid Steer Tools"
    SKIDSTEERVEHICLES = "Skid Steers"
    SLURRYTANKS = "Slurry Tanks"
    SLURRYTOOLS = "Slurry Tools"
    SLURRYTRANSPORT = "Slurry Transport"
    SPADERS = "Spaders"
    SPECIALHEADERS = "Special Headers"
    SPINACHHARVESTERS = "Spinach Harvesters"
    SPRAYERS = "Sprayers"
    STONEPICKERS = "Stone Pickers"
    STRAWBLOWERS = "Straw Blowers"
    SUBSOILERS = "Subsoilers"
    SUGARCANEHARVESTERS = "Sugarcane Harvesters"
    SUGARCANEPLANTERS = "Sugarcane Planters"
    SUGARCANETRANSPORT = "Sugarcane Transport"
    TEDDERS = "Tedders"
    TELELOADERTOOLS = "Telehandler Tools"
    TELELOADERVEHICLES = "Telehandlers"
    TRACTORSL = "Large Tractors"
    TRACTORSM = "Medium Tractors"
    TRACTORSS = "Small Tractors"
    TRAILERS = "Trailers"
    TRAILERSCHANGINGSYSTEM = "Hooklift Trailers"
    TRAILERSSEMI = "Semi-Trailers"
    TRUCKS = "Trucks"
    VEGETABLEHARVESTERS = "Vegetable Harvesters"
    VEGETABLEPLANTERS = "Vegetable Planters"
    WEEDERS = "Weeders"
    WEIGHTS = "Weights"
    WHEELLOADERTOOLS = "Wheel Loader Tools"
    WHEELLOADERVEHICLES = "Wheel Loaders"
    WINDROWERS = "Windrowers"
    WINTEREQUIPMENT = "Winter Equipment"
    WOODCHIPPERS = "Wood Chippers"
    WOODTRANSPORT = "Wood Transport"

    @property
    def slug(self) -> str:
        """
        :return: The slug for this category, e.g. "medium_tractors".
        """
        words = "".join(c if c.isalnum() else " " for c in self.value.lower()).split()
        return "_".join(words)

    @classmethod
    def from_key(cls, key: str) -> VehicleCategory | None:
        """
        :param key: A raw shop category, ignoring case, e.g. "TRACTORSM".
        :return: The matching category, or None if it is unknown (e.g. mod-added).
        """
        return cls.__members__.get(key.upper())

    @classmethod
    def from_slug(cls, slug: str) -> VehicleCategory | None:
        """
        :param slug: A category slug, ignoring case, e.g. "medium_tractors".
        :return: The matching category, or None if no category has that slug.
        """
        slug = slug.lower()
        return next((category for category in cls if category.slug == slug), None)
