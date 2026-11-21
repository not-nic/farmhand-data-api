"""
Tests for vehicle fill type filtering, l10n labels and motor display names.
"""

from uuid import uuid4

import pytest

from src.api.constants import AssetType
from src.api.core.db.models import Asset, MapVehicle, Vehicle
from src.api.core.db.models.vehicles import (
    VehicleFillUnitConfiguration,
    VehicleMotorConfiguration,
)
from src.api.core.schema.maps.maps import MapVehicleResponse
from src.api.core.schema.vehicles import FillUnitConfigurationResponseModel, MapVehicleModel
from src.api.core.schema.vehicles.vehicle_xml import (
    FillUnitConfigModel,
    FillUnitModel,
    MotorConfigModel,
)
from src.api.parsers.xml.vehicles.l10n_parser import L10n, L10nXmlParser
from src.api.parsers.xml.vehicles.store_configurations_parser import (
    StoreConfigurationsXmlParser,
)
from src.api.parsers.xml.vehicles.vehicle_xml_parser import VehicleXmlParser
from src.api.services.vehicles.vehicle_service import VehicleService
from src.api.utils import display_name, label_from_key, strip_dlc_prefix


class TestVehicleLabels:
    """
    Tests for vehicle XML parsing, l10n labels and vehicle display names.
    """

    TRACTOR_XML = b"""<?xml version="1.0" encoding="utf-8"?>
    <vehicle type="tractor">
        <base><typeDesc>$l10n_typeDesc_tractor</typeDesc></base>
        <motorized><motorConfigurations>
            <motorConfiguration name="720 Vario" hp="203" price="0"/>
            <motorConfiguration name="Farmall 90 C" hp="90" vehicleName="Farmall 90 C"/>
        </motorConfigurations></motorized>
        <fillUnit><fillUnits>
            <fillUnit fillTypes="diesel" capacity="400"/>
            <fillUnit fillTypes="DEF" capacity="40"/>
            <fillUnit fillTypes="air" capacity="2500"/>
            <fillUnit fillTypes="electricCharge AIR" capacity="10"/>
        </fillUnits></fillUnit>
    </vehicle>"""

    CONFIGURED_XML = b"""<vehicle type="sowingMachine">
        <fillUnit><fillUnitConfigurations>
            <fillUnitConfiguration name="air only"><fillUnits>
                <fillUnit fillTypes="air" capacity="1"/>
            </fillUnits></fillUnitConfiguration>
            <fillUnitConfiguration name="seeds"><fillUnits>
                <fillUnit fillTypes="seeds" capacity="3000"/>
            </fillUnits></fillUnitConfiguration>
        </fillUnitConfigurations></fillUnit>
    </vehicle>"""

    L10N_XML = b"""<l10n><elements>
        <e k="fillType_electricCharge" v="Electric Charge"/>
        <e k="category_tractorsS" v="Small Tractors"/>
    </elements></l10n>"""

    STORE_CONFIGS_XML = b"""<storeConfigurations>
        <item name="Farmall C Series" brand="Case IH" xmlFilename="data/vehicles/caseIH/farmall120C/farmall120C.xml">
            <configuration name="motor" defaultIndex="1">
                <option index="1" name="Farmall 90 C" power="90" price="0" vehicleName="Farmall 90 C"/>
                <option index="2" name="Farmall 100 C" power="100" price="3500" isSelectable="false"/>
            </configuration>
            <configuration name="fillUnit" defaultIndex="1">
                <option index="1" name="Plastic" price="0"/>
                <option index="2" name="2" hasDefaultName="true" price="0"/>
            </configuration>
            <configuration name="design"><option index="1" name="x" price="0"/></configuration>
        </item>
        <item name="Bale" brand="None" xmlFilename="data/objects/bale.xml"/>
    </storeConfigurations>"""

    ICON_URI = "s3://farmhand-assets/vehicles/fendt/vario700/store_vario700.png"

    @pytest.fixture
    def vehicle(self) -> Vehicle:
        """
        A Fendt 700 Vario, with a stale singular category_label.
        """
        return Vehicle(
            id=uuid4(),
            config_path="vehicles/fendt/vario700/vario700.xml",
            name="700 Vario",
            brand="Fendt",
            category="TRACTORSM",
            category_label="Medium Tractor",
            vehicle_type="tractor",
            image="vehicles/fendt/vario700/store_vario700.png",
        )

    @pytest.fixture
    def icon(self, vehicle: Vehicle) -> Asset:
        """
        The vehicle's ingested store icon.
        """
        return Asset(
            vehicle=vehicle,
            asset_type=AssetType.ICON,
            filename="store_vario700.png",
            asset_uri=self.ICON_URI,
            is_ingested=True,
        )

    @pytest.fixture
    def map_vehicle(self, vehicle: Vehicle, icon: Asset) -> MapVehicle:
        """
        The vehicle placed on a map, with no motor or fill unit configuration selected.
        """
        return MapVehicle(vehicle=vehicle)

    def test_fill_units_drop_air_and_upper_case(self):
        parsed = VehicleXmlParser().parse(self.TRACTOR_XML)
        units = parsed.fill_unit_configurations[0].fill_units
        assert [u.fill_types for u in units] == [["DIESEL"], ["DEF"], ["ELECTRICCHARGE"]]

    def test_empty_fill_unit_configuration_skipped_keeping_index(self):
        configs = VehicleXmlParser().parse(self.CONFIGURED_XML).fill_unit_configurations
        assert [(c.index, c.name) for c in configs] == [(2, "seeds")]

    def test_parser_reads_vehicle_type_and_vehicle_name(self):
        parsed = VehicleXmlParser().parse(self.TRACTOR_XML)
        assert parsed.vehicle_type == "tractor"
        assert [m.vehicle_name for m in parsed.motor_configurations] == [None, "Farmall 90 C"]

    def test_l10n_lookup_is_case_insensitive_with_fallback(self):
        texts = L10nXmlParser().parse(self.L10N_XML)
        assert texts.fill_type("ELECTRICCHARGE") == "Electric Charge"
        assert L10n().fill_type("GRASS_WINDROW") == "Grass Windrow"

    @pytest.mark.parametrize(
        ("key", "expected"),
        [
            ("TRACTORSM", "Medium Tractors"),
            ("tractorsS", "Small Tractors"),
            ("PLOWS", "Plows"),
            ("NEWCATEGORY", "Newcategory"),
        ],
    )
    def test_category_label_prefers_curated(self, key, expected):
        # The curated label wins over the l10n text.
        assert L10nXmlParser().parse(self.L10N_XML).category(key) == expected

    def test_category_label_falls_back_to_l10n(self):
        texts = L10n({"category_newcategory": "New Category"})
        assert texts.category("NEWCATEGORY") == "New Category"

    @pytest.mark.parametrize(
        ("value", "expected"),
        [("teleHandler", "Tele Handler"), ("GRASS_WINDROW", "Grass Windrow"), ("DIESEL", "Diesel")],
    )
    def test_label_from_key(self, value, expected):
        assert label_from_key(value) == expected

    def test_display_name_does_not_repeat_brand(self):
        assert display_name("Fendt", "728 Vario") == "Fendt 728 Vario"
        assert display_name("Case IH", "Case IH Farmall") == "Case IH Farmall"
        assert display_name(None, "Versa") == "Versa"

    @pytest.mark.parametrize(
        ("motor", "expected"),
        [
            (VehicleMotorConfiguration(index=5, name="728 Vario", hp=303, max_speed=60, price=0),
             "Fendt 728 Vario"),
            (VehicleMotorConfiguration(index=1, name="90 C", vehicle_name="Farmall 90 C", hp=90,
                                       max_speed=40, price=0),
             "Fendt Farmall 90 C"),
            (None, "Fendt 700 Vario"),
        ],
    )
    def test_map_vehicle_name_is_shop_display_name(self, map_vehicle, motor, expected):
        map_vehicle.motor_configuration = motor
        response = MapVehicleResponse.from_map_vehicle(map_vehicle)
        assert response.name == expected
        # The curated plural label wins over the stale singular category_label on the fixture.
        assert response.category == "Medium Tractors"
        assert response.image == self.ICON_URI

    def test_map_vehicle_response_is_a_summary(self, map_vehicle):
        body = MapVehicleResponse.from_map_vehicle(map_vehicle).model_dump()
        assert body == {
            "id": map_vehicle.vehicle.id, "name": "Fendt 700 Vario", "brand": "Fendt",
            "category": "Medium Tractors", "image": self.ICON_URI,
        }

    def test_fill_unit_response_returns_fill_type_labels(self):
        fill_unit = VehicleFillUnitConfiguration(
            index=1, name=None, price=0,
            fill_units=[{"fill_types": [{"key": "FERTILIZER", "label": "Solid Fertilizer"}],
                         "capacity": 1250.0}],
        )
        assert FillUnitConfigurationResponseModel.model_validate(fill_unit).model_dump() == {
            "name": None, "price": 0,
            "fill_units": [{"fill_types": ["Solid Fertilizer"], "capacity": 1250.0}],
        }

    def test_map_vehicle_image_is_none_until_icon_ingested(self, map_vehicle, icon):
        icon.is_ingested = False
        response = MapVehicleResponse.from_map_vehicle(map_vehicle)
        assert response.image is None

    @pytest.mark.parametrize(
        ("farm_id", "expected"),
        [(1, True), (0, False), (50, False), (2, False), (None, False)],
    )
    def test_map_vehicle_is_starting_farm(self, farm_id, expected):
        item = MapVehicleModel(filename="x.xml", farm_id=farm_id)
        assert item.is_starting_farm is expected

    def test_store_configurations_parser(self):
        items = StoreConfigurationsXmlParser().parse(self.STORE_CONFIGS_XML)
        motors, fill_units = items["vehicles/caseIH/farmall120C/farmall120C.xml"]
        assert [(m.index, m.name, m.vehicle_name, m.hp, m.price) for m in motors] == [
            (1, "Farmall 90 C", "Farmall 90 C", 90, 0),
            (2, "Farmall 100 C", None, 100, 3500),
        ]
        assert [(f.index, f.name) for f in fill_units] == [(1, "Plastic"), (2, None)]
        assert len(items) == 1

    def test_merge_prefers_store_names_and_keeps_xml_contents(self):
        motors = VehicleService._merge_motors(
            [MotorConfigModel(index=1, name="728 Vario", hp=303)],
            [MotorConfigModel(index=1, name="$l10n_x", hp=1, max_speed=60)],
        )
        assert [(m.name, m.hp, m.max_speed) for m in motors] == [("728 Vario", 303, 60)]

        fills = VehicleService._merge_fill_units(
            [FillUnitConfigModel(index=1, name="Plastic", price=0)],
            [FillUnitConfigModel(index=1, name="$l10n_configuration_valueDefault",
                                 fill_units=[FillUnitModel(fill_types=["DIESEL"], capacity=400)])],
        )
        assert fills[0].name == "Plastic" and fills[0].fill_units[0].fill_types == ["DIESEL"]

    def test_strip_dlc_prefix(self):
        assert strip_dlc_prefix("pdlc/skyAgriculturePack/vehicles/a/b/b.xml") == "vehicles/a/b/b.xml"
        assert strip_dlc_prefix("vehicles/a/b/b.xml") == "vehicles/a/b/b.xml"
