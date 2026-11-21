"""
Tests for VehicleResponseModel, including the grouped `specs` block.
"""

from uuid import uuid4

import pytest

from src.api.core.db.models import Vehicle
from src.api.core.schema.vehicles import VehicleResponseModel


@pytest.fixture
def vehicle() -> Vehicle:
    """
    A Lemken Kredo with no specs set.
    """
    return Vehicle(
        id=uuid4(),
        config_path="vehicles/kredo/kredo.xml",
        name="Kredo",
        brand="Lemken",
        category="CULTIVATORS",
        category_label="Cultivator",
        price=10000,
        dlc=None,
    )


def test_vehicle_response_specs_are_populated(vehicle):
    vehicle.weight = 10600
    vehicle.working_speed = 15
    vehicle.working_width = 12.0
    vehicle.needed_power = 300
    body = VehicleResponseModel.from_vehicle(vehicle).model_dump()
    assert body["specs"] == {
        "weight": 10600,
        "working_speed": 15,
        "working_width": 12.0,
        "needed_power": 300,
    }


def test_vehicle_response_specs_are_none_when_unavailable(vehicle):
    body = VehicleResponseModel.from_vehicle(vehicle).model_dump()
    assert body["specs"] == {
        "weight": None,
        "working_speed": None,
        "working_width": None,
        "needed_power": None,
    }
