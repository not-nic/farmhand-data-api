"""
Tests for parsing vehicle specs: weight, working_speed, working_width
and needed_power.
"""

import pytest

from src.api.parsers.xml.vehicles.vehicle_xml_parser import VehicleXmlParser


class TestVehicleSpecs:
    """
    Tests for VehicleXmlParser's storeData/specs and base spec parsing.
    """

    def test_seeder_specs(self):
        """
        A seeder's needed power, working width, speed limit and summed component
        masses should all be parsed.
        """
        xml = b"""<vehicle type="fertilizingSowingMachine">
            <storeData>
                <specs>
                    <neededPower>300</neededPower>
                    <workingWidth>12</workingWidth>
                </specs>
            </storeData>
            <base>
                <speedLimit value="15"/>
                <components>
                    <component mass="7600"/>
                    <component mass="1500"/>
                    <component mass="750"/>
                    <component mass="750"/>
                </components>
            </base>
        </vehicle>"""

        parsed = VehicleXmlParser().parse(xml)
        assert parsed.needed_power == 300
        assert parsed.working_width == 12.0
        assert parsed.working_speed == 15
        assert parsed.weight == 10600

    def test_working_speed_from_spec_speed_limit(self):
        """
        storeData/specs/speedLimit should be used over base/speedLimit.
        """
        xml = b"""<vehicle type="sprayer">
            <storeData>
                <specs>
                    <speedLimit>12</speedLimit>
                </specs>
            </storeData>
            <base>
                <speedLimit value="40"/>
            </base>
        </vehicle>"""

        assert VehicleXmlParser().parse(xml).working_speed == 12

    def test_working_speed_from_base_speed_limit(self):
        """
        base/speedLimit@value should be used when specs has no speedLimit.
        """
        xml = b"""<vehicle type="sprayer">
            <storeData>
                <specs>
                    <neededPower>90</neededPower>
                </specs>
            </storeData>
            <base>
                <speedLimit value="40"/>
            </base>
        </vehicle>"""

        assert VehicleXmlParser().parse(xml).working_speed == 40

    def test_working_width_from_width_attribute(self):
        """
        A variable-width tool's workingWidth@width should be used as its width.
        """
        xml = b"""<vehicle type="cultivator">
            <storeData>
                <specs>
                    <workingWidth minWidth="6" width="6"/>
                </specs>
            </storeData>
        </vehicle>"""

        assert VehicleXmlParser().parse(xml).working_width == 6.0

    @pytest.mark.parametrize(
        ("spec", "expected"),
        [
            ('<workingWidth minWidth="2.8499999046325684" width="2.8499999046325684"/>', 2.85),
            ('<workingWidth minWidth="6.699999809265137" width="6.699999809265137"/>', 6.7),
            ("<workingWidth>18.28</workingWidth>", 18.28),
            ("<workingWidth>0.75</workingWidth>", 0.75),
        ],
    )
    def test_working_width_rounding(self, spec, expected):
        """
        Working width should be rounded to 2 dp to strip float32 noise.
        """
        xml = f'<vehicle type="cultivator"><storeData><specs>{spec}</specs></storeData></vehicle>'
        assert VehicleXmlParser().parse(xml.encode()).working_width == expected

    def test_weight_from_component_mass(self):
        """
        weight@componentMass plus wheelMassDefaultConfig (tonnes) should be used
        over the summed base component masses.
        """
        xml = b"""<vehicle type="sowingMachine">
            <storeData>
                <specs>
                    <weight componentMass="6.895" wheelMassDefaultConfig="0.884"/>
                </specs>
            </storeData>
            <base>
                <components>
                    <component mass="1"/>
                </components>
            </base>
        </vehicle>"""

        assert VehicleXmlParser().parse(xml).weight == round((6.895 + 0.884) * 1000)

    def test_weight_ignore(self):
        """
        weight@ignore="true" should leave the weight unset.
        """
        xml = b"""<vehicle type="trailer">
            <storeData>
                <specs>
                    <weight ignore="true"/>
                </specs>
            </storeData>
            <base>
                <components>
                    <component mass="5000"/>
                </components>
            </base>
        </vehicle>"""

        assert VehicleXmlParser().parse(xml).weight is None

    def test_needed_power_from_base_attribute(self):
        """
        neededPower@base should be used when neededPower has no text.
        """
        xml = b"""<vehicle type="cultivator">
            <storeData>
                <specs>
                    <neededPower base="200"/>
                </specs>
            </storeData>
        </vehicle>"""

        assert VehicleXmlParser().parse(xml).needed_power == 200

    def test_weight_zero_component_mass(self):
        """
        A zero componentMass with no base components should leave the weight unset.
        """
        xml = b"""<vehicle type="sowingMachine">
            <storeData>
                <specs>
                    <weight componentMass="0" wheelMassDefaultConfig="0"/>
                </specs>
            </storeData>
        </vehicle>"""

        assert VehicleXmlParser().parse(xml).weight is None

    def test_weight_zero_component_mass_with_components(self):
        """
        A zero componentMass should use the summed base component masses.
        """
        xml = b"""<vehicle type="sowingMachine">
            <storeData>
                <specs>
                    <weight componentMass="0" wheelMassDefaultConfig="0"/>
                </specs>
            </storeData>
            <base>
                <components>
                    <component mass="3570"/>
                </components>
            </base>
        </vehicle>"""

        assert VehicleXmlParser().parse(xml).weight == 3570

    def test_no_specs(self):
        """
        A vehicle with no specs or base should have no spec values.
        """
        xml = b"""<vehicle type="trailer">
            <storeData>
                <name>Trailer</name>
            </storeData>
        </vehicle>"""

        parsed = VehicleXmlParser().parse(xml)
        assert parsed.needed_power is None
        assert parsed.working_width is None
        assert parsed.working_speed is None
        assert parsed.weight is None

    def test_non_numeric_specs(self):
        """
        Non-numeric spec values should be left unset.
        """
        xml = b"""<vehicle type="cultivator">
            <storeData>
                <specs>
                    <neededPower>n/a</neededPower>
                    <workingWidth>wide</workingWidth>
                    <speedLimit>fast</speedLimit>
                    <weight componentMass="heavy"/>
                </specs>
            </storeData>
            <base>
                <speedLimit value="quick"/>
            </base>
        </vehicle>"""

        parsed = VehicleXmlParser().parse(xml)
        assert parsed.needed_power is None
        assert parsed.working_width is None
        assert parsed.working_speed is None
        assert parsed.weight is None
