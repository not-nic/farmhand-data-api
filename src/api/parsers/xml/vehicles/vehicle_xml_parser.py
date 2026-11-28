"""
Parser for Farming Simulator vehicle definition XML files, including
resolution of reskinned vehicles that inherit from a <parentFile>.
"""

import re
from collections.abc import Callable
from xml.etree.ElementTree import Element, SubElement

from src.api.constants import IgnoredFillType
from src.api.core.logger import logger
from src.api.core.schema.validators import Validators
from src.api.core.schema.vehicles.vehicle_xml import (
    FillUnitConfigModel,
    FillUnitModel,
    MotorConfigModel,
    VehicleXmlModel,
)
from src.api.parsers.xml.base_parser import BaseXmlParser
from src.api.utils import normalise_config_path

ParentResolver = Callable[[str], bytes | None]

_SEGMENT = re.compile(r"^(\w+)(?:\((\d+)\))?$")
_MAX_PARENT_DEPTH = 10


class VehicleXmlParser(BaseXmlParser[VehicleXmlModel]):
    """
    Parses a vehicle definition XML into a VehicleXmlModel.
    """

    def parse(
        self, content: bytes, resolve_parent: ParentResolver | None = None
    ) -> VehicleXmlModel:
        """
        Parse vehicle definition XML bytes into a VehicleXmlModel.

        :param content: Raw bytes of the vehicle XML file.
        :param resolve_parent: Optional callable taking a normalised parent config path
            (e.g. "vehicles/challenger/mt655/mt655.xml") and returning its bytes, or None.
            Used to merge reskinned vehicles with their parent.
        :return: Parsed VehicleXmlModel.
        :raises ParseError: If the content is not valid XML.
        :raises ValueError: If the XML is valid but isn't a vehicle definition.
        """
        root = self._load(content)
        self._ensure_vehicle(root)
        parent_path = self._parent_path(root)
        root = self._resolve_tree(root, resolve_parent, 0)

        return VehicleXmlModel(
            vehicle_type=root.get("type"),
            image=self._image(root),
            parent_path=parent_path,
            motor_configurations=self._motor_configurations(root),
            fill_unit_configurations=self._fill_unit_configurations(root),
            weight=self._weight(root),
            working_speed=self._working_speed(root),
            working_width=self._working_width(root),
            needed_power=self._needed_power(root),
        )

    @staticmethod
    def _ensure_vehicle(root: Element) -> None:
        """
        :param root: The root element of a parsed XML file.
        :raises ValueError: If the root element isn't <vehicle>.
        """
        if root.tag != "vehicle":
            raise ValueError(f"Not a vehicle definition: root element is <{root.tag}>.")

    @staticmethod
    def _parent_path(root: Element) -> str | None:
        """
        :param root: The root <vehicle> element.
        :return: The normalised parentFile config path, or None.
        """
        parent_file = root.find("parentFile")
        if parent_file is None:
            return None
        return normalise_config_path(parent_file.get("xmlFilename", ""))

    def _resolve_tree(
        self, root: Element, resolve_parent: ParentResolver | None, depth: int
    ) -> Element:
        """
        Merge a reskinned vehicle with its (recursively resolved) parent tree.

        :param root: The child's root <vehicle> element.
        :param resolve_parent: Callable returning parent bytes for a config path.
        :param depth: Current recursion depth, guards against parent cycles.
        :return: The merged tree, or the child's own tree if there is no resolvable parent.
        """
        parent_file = root.find("parentFile")
        if parent_file is None:
            return root

        parent_path = self._parent_path(root)
        parent_bytes = (
            resolve_parent(parent_path)
            if resolve_parent and parent_path and depth < _MAX_PARENT_DEPTH
            else None
        )
        if parent_bytes is None:
            logger.warning(
                "[Vehicle Parser]: parent '%s' not resolved, parsing child alone.",
                parent_file.get("xmlFilename"),
            )
            return root

        merged = self._load(parent_bytes)
        self._ensure_vehicle(merged)
        merged = self._resolve_tree(merged, resolve_parent, depth + 1)

        for op in parent_file.findall("attributes/*"):
            path = op.get("path", "")
            if op.tag == "set":
                self._set_path(merged, path, op.get("value", ""))
            elif op.tag == "remove":
                self._remove_path(merged, path)

        if root.get("type"):
            merged.set("type", root.get("type"))
        return merged

    @staticmethod
    def _walk(root: Element, path: str, create: bool) -> tuple[Element | None, str | None]:
        """
        Walk a dotted path (e.g. "vehicle.a.b(1)#attr") from the root.

        :param root: The root <vehicle> element.
        :param path: Dot-separated tag segments starting at "vehicle", optional "(i)" 0-based
            index per segment and an optional trailing "#attr".
        :param create: Create missing elements while walking.
        :return: The target element (None if missing) and the attribute name, if any.
        """
        path, _, attr = path.partition("#")
        segments = path.split(".")
        node: Element | None = root
        for segment in segments[1:]:
            match = _SEGMENT.match(segment)
            if node is None or match is None:
                return None, attr or None
            tag, index = match.group(1), int(match.group(2) or 0)
            children = node.findall(tag)
            while create and len(children) <= index:
                children.append(SubElement(node, tag))
            node = children[index] if index < len(children) else None
        return node, attr or None

    def _set_path(self, root: Element, path: str, value: str) -> None:
        """
        Apply a <set> override: sets an attribute ("#attr") or the element text.

        :param root: The root <vehicle> element to modify.
        :param path: The override path.
        :param value: The value to set.
        """
        node, attr = self._walk(root, path, create=True)
        if node is None:
            return
        if attr:
            node.set(attr, value)
        else:
            node.text = value

    def _remove_path(self, root: Element, path: str) -> None:
        """
        Apply a <remove> override: removes an attribute ("#attr") or the element.

        :param root: The root <vehicle> element to modify.
        :param path: The override path.
        """
        node, attr = self._walk(root, path, create=False)
        if node is None:
            return
        if attr:
            node.attrib.pop(attr, None)
            return
        parent_path = path.rpartition(".")[0]
        parent, _ = self._walk(root, parent_path, create=False)
        if parent is not None:
            parent.remove(node)

    def _image(self, root: Element) -> str | None:
        """
        :param root: The root <vehicle> element.
        :return: The normalised store image path, or None.
        """
        store_data = root.find("storeData")
        image = self._text(store_data, "image") if store_data is not None else None
        return normalise_config_path(image) if image else None

    @staticmethod
    def _to_int(value: str | None) -> int | None:
        """
        :param value: A numeric string such as "203" or "53.5".
        :return: The rounded integer, or None if missing / not numeric.
        """
        try:
            return round(float(value)) if value not in (None, "") else None
        except ValueError:
            return None

    @staticmethod
    def _to_float(value: str | None) -> float | None:
        """
        :param value: A numeric string such as "6" or "6.895".
        :return: The float value, or None if missing / not numeric.
        """
        try:
            return float(value) if value not in (None, "") else None
        except ValueError:
            return None

    def _weight(self, root: Element) -> int | None:
        """
        Resolve the vehicle's weight in kg.

        :param root: The root <vehicle> element.
        :return: None if storeData/specs/weight@ignore is "true". Else, if
            storeData/specs/weight@componentMass is present and, after adding
            wheelMassDefaultConfig (if any) and converting from tonnes, is above
            zero, that value. Else the sum of base/components/component@mass (kg),
            or None if none have a mass (e.g. bundle XMLs with no <base>).
        """
        if self._attr(root, "storeData/specs/weight", "ignore") == "true":
            return None

        component_mass = self._to_float(self._attr(root, "storeData/specs/weight", "componentMass"))
        if component_mass is not None:
            wheel_mass = self._to_float(
                self._attr(root, "storeData/specs/weight", "wheelMassDefaultConfig")
            )
            total = round((component_mass + (wheel_mass or 0.0)) * 1000)
            if total > 0:
                return total

        masses = [
            mass
            for component in root.findall("base/components/component")
            if (mass := self._to_float(component.get("mass"))) is not None
        ]
        return round(sum(masses)) if masses else None

    def _working_speed(self, root: Element) -> int | None:
        """
        :param root: The root <vehicle> element.
        :return: Working speed in km/h: storeData/specs/speedLimit text if present,
            else base/speedLimit@value, else None.
        """
        text = self._text(root, "storeData/specs/speedLimit")
        if text is not None:
            return self._to_int(text)
        return self._to_int(self._attr(root, "base/speedLimit", "value"))

    def _working_width(self, root: Element) -> float | None:
        """
        :param root: The root <vehicle> element.
        :return: Working width in metres to 2 dp: storeData/specs/workingWidth text if
            present, else its "width" attribute (for variable-width tools), else None.
            Rounded as the game writes some widths with float32 noise, e.g.
            "2.8499999046325684" for 2.85.
        """
        text = self._text(root, "storeData/specs/workingWidth")
        if text is None:
            text = self._attr(root, "storeData/specs/workingWidth", "width")
        width = self._to_float(text)
        return round(width, 2) if width is not None else None

    def _needed_power(self, root: Element) -> int | None:
        """
        :param root: The root <vehicle> element.
        :return: Needed power in hp: storeData/specs/neededPower text if numeric,
            else its "base" attribute (e.g. <neededPower base="200"/>), else None.
        """
        value = self._to_int(self._text(root, "storeData/specs/neededPower"))
        if value is not None:
            return value
        return self._to_int(self._attr(root, "storeData/specs/neededPower", "base"))

    def _motor_configurations(self, root: Element) -> list[MotorConfigModel]:
        """
        :param root: The root <vehicle> element.
        :return: Motor configurations in XML order with 1-based indexes.
        """
        store_speed = self._to_int(self._text(root, "storeData/specs/maxSpeed"))
        motors = []
        for index, config in enumerate(
            root.findall("motorized/motorConfigurations/motorConfiguration"), start=1
        ):
            max_speed = self._to_int(self._attr(config, "motor", "maxForwardSpeed"))
            motors.append(
                MotorConfigModel(
                    index=index,
                    name=config.get("name"),
                    vehicle_name=config.get("vehicleName") or None,
                    hp=self._to_int(config.get("hp")),
                    max_speed=max_speed if max_speed is not None else store_speed,
                    price=self._to_int(config.get("price")),
                )
            )
        return motors

    def _fill_unit_configurations(self, root: Element) -> list[FillUnitConfigModel]:
        """
        Read fill unit configurations, falling back to a single index-1 configuration
        for vehicles with a plain <fillUnit><fillUnits> list. Configurations left with
        no fill units are skipped, keeping the XML index of the rest.

        :param root: The root <vehicle> element.
        :return: Fill unit configurations in XML order with 1-based indexes.
        """
        configs = root.findall("fillUnit/fillUnitConfigurations/fillUnitConfiguration")
        if configs:
            return [
                FillUnitConfigModel(
                    index=index,
                    name=config.get("name"),
                    price=self._to_int(config.get("price")),
                    fill_units=fill_units,
                )
                for index, config in enumerate(configs, start=1)
                if (fill_units := self._fill_units(config.find("fillUnits")))
            ]

        plain = self._fill_units(root.find("fillUnit/fillUnits"))
        return [FillUnitConfigModel(index=1, fill_units=plain)] if plain else []

    @staticmethod
    def _fill_units(container: Element | None) -> list[FillUnitModel]:
        """
        :param container: A <fillUnits> element, or None.
        :return: The fill units it contains, with upper-case fill types. Ignored fill
            types (see IgnoredFillType) are removed, along with units left empty.
        """
        if container is None:
            return []
        units = []
        for unit in container.findall("fillUnit"):
            fill_types = [
                fill_type
                for fill_type in Validators.to_list(unit.get("fillTypes"), str.upper)
                if fill_type not in IgnoredFillType
            ]
            if fill_types:
                units.append(
                    FillUnitModel(
                        fill_types=fill_types, capacity=float(unit.get("capacity") or 0)
                    )
                )
        return units
