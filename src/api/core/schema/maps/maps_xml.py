"""
Module containing Map XML file pydantic models.
"""

from pydantic import BaseModel, field_validator, model_validator

from src.api.core.schema.validators import DDSFilename, Filename, Validators


class AnimalsModel(BaseModel):
    """
    Pydantic model for the <animals> element in maps.xml.
    """

    filename: Filename
    food_filename: Filename


class ApplicationRateSoilModel(BaseModel):
    """
    Application rate for a given soil type, in kg/ha.
    """

    soil_type_index: int
    rate: float


class ApplicationRateModel(BaseModel):
    """
    Precision Farming application rate configuration for a single fill
    type (e.g. compost, lime) — the regular rate plus per-soil-type overrides.
    """

    fill_type: str
    auto_adjust_to_fruit: bool = False
    regular_rate: float
    soils: list[ApplicationRateSoilModel] = []


class FertilizerUsageModel(BaseModel):
    """
    Nitrogen usage amount for a given fill type.
    """

    fill_type: str
    amount: float


class FruitRequirementSoilModel(BaseModel):
    """
    Precision Farming nitrogen target and reduction values for a fruit
    type on a given sol type.
    """

    soil_type_index: int
    target_level: float
    reduction: float
    yield_potential: float
    reduction_forage: float | None = None


class FruitRequirementModel(BaseModel):
    """
    Precision Farming nitrogen requirement model for a fruit type.
    """

    fruit_type_name: str
    always_allow_fertilization: bool = False
    ignore_overfertilization: bool = False
    available_as_default_rate: bool = True
    soils: list[FruitRequirementSoilModel] = []


class SeedRateTierModel(BaseModel):
    """
    Pydantic model for a SeedRate, containing a rate and seed usage.
    """

    rate: int
    usage: float


class SeedRateModel(BaseModel):
    """
    Pydantic model containing a low, medium, and high Seed Rate Model.
    """

    low: SeedRateTierModel
    medium: SeedRateTierModel
    high: SeedRateTierModel

    @model_validator(mode="before")
    @classmethod
    def build_tiers(cls, data: dict) -> dict:
        """
        Convert the raw rates and usages space-separated strings into a tiered
        rate of low, medium, and high.

        Example:
            <seedRates rates="301 331 361" usages="..."/> into the three named tiers.
        """
        if not isinstance(data, dict) or "low" in data:
            return data

        rates = Validators.to_list(data.get("rates"), int)
        usages = Validators.to_list(data.get("usages"), float)

        if len(rates) != 3 or len(usages) != 3:
            raise ValueError(
                f"Expected three seed rate tiers, got rates={rates}, usages={usages}"
            )

        tiers = ("low", "medium", "high")
        return {
            tier: {"rate": rates[item], "usage": usages[item]}
            for item, tier in enumerate(tiers)
        }


class SoilYieldModel(BaseModel):
    """
    Yield multipliers for a fruit type at a given soil type, one value
    per seed rate (low/medium/high).
    """

    soil_type_index: int
    yields: list[float] = []

    @field_validator("yields", mode="before")
    @classmethod
    def validate_float(cls, value: str) -> list[float]:
        """
        Validate a space-separated string of float values into a list
        of floats.
        :param value: The value to convert.
        :return: (list) A list of floats as a response.
        """
        return Validators.to_list(value, float)


class PrecisionFruitTypeModel(BaseModel):
    """
    Precision farming seed rate configuration for a single fruit type.
    """

    name: str
    seed_rates: SeedRateModel | None = None
    soil_yields: list[SoilYieldModel] = []


class CoverCropBonusModel(BaseModel):
    """
    Subsidy bonus per hectare for planting a cover crop.
    """

    fruit_type: str
    bonus_per_ha: list[float] = []

    @field_validator("bonus_per_ha", mode="before")
    @classmethod
    def validate_float(cls, value: str) -> list[float]:
        """
        Validate a space-separated string of float values into a list
        of floats.

        :param value: The value to convert.
        :return: (list) A list of floats as a response.
        """
        return Validators.to_list(value, float)


class PrecisionFarmingModel(BaseModel):
    """
    Pydantic model for a <precisionFarming> element in a maps.xml.
    """

    soil_map_filename: Filename = None
    application_rates: list[ApplicationRateModel] = []
    fertilizer_usage: list[FertilizerUsageModel] = []
    fruit_requirements: list[FruitRequirementModel] = []
    fruit_types: list[PrecisionFruitTypeModel] = []
    cover_crop_bonuses: list[CoverCropBonusModel] = []


class MapsXmlModel(BaseModel):
    """
    Pydantic class containing the maps.xml Model.
    """

    width: int
    height: int
    overview_filename: DDSFilename = None
    map_i3d_filename: Filename = None
    farmlands_filename: Filename = None
    fields_filename: Filename = None
    fill_types_filename: Filename = None

    animals: AnimalsModel | None = None
