"""
Pydantic models for data parsed from a map's vehicles.xml file.
"""

from pydantic import BaseModel, Field

STARTING_FARM_ID = 1
"""The farm a new career's player starts on, which owns the map's starting vehicles."""


class MapVehicleModel(BaseModel):
    """
    A single starting vehicle of a map.

    Attributes:
        filename: The raw vehicle XML path, e.g. "data/vehicles/johnDeere/series6R/series6RLarge.xml".
        farm_id: The owning farm, if specified.
        configurations: Selected configuration ids by name. Kept as strings as some are non-numeric.
    """

    filename: str
    farm_id: int | None = None
    configurations: dict[str, str] = Field(default_factory=dict)

    @property
    def is_starting_farm(self) -> bool:
        """
        A new career always gives the player farm 1, so everything on it is starting
        equipment. Farm 0 is the map itself (props and decoration), and maps park
        dealership / showroom vehicles on farms that don't exist, e.g. farm 50.
        :return: True if the vehicle belongs to the player's starting farm.
        """
        return self.farm_id == STARTING_FARM_ID
