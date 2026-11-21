"""
Vehicle Repository containing database interactions.
see: base_repository.py to see the base repository to inherit from.
"""

from collections.abc import Iterable

from sqlalchemy import func, inspect, or_
from sqlalchemy.orm import Session

from src.api.constants import VehicleCategory
from src.api.core.db.models.vehicles import (
    Vehicle,
    VehicleFillUnitConfiguration,
    VehicleMotorConfiguration,
)
from src.api.core.repositories import Repository


class VehicleRepository(Repository[Vehicle]):
    """
    Repository for Vehicle database interactions.
    """

    def __init__(self, db: Session):
        super().__init__(db, Vehicle)

    def get_by_config_path(self, config_path: str) -> Vehicle | None:
        """
        Get a vehicle by its config_path.
        :param config_path: The canonical config path of the vehicle.
        :return: Vehicle if it exists, else None.
        """
        return self.db.query(self.model).filter(self.model.config_path == config_path).first()

    def get_by_config_paths(self, paths: Iterable[str]) -> dict[str, Vehicle]:
        """
        Get many vehicles by their config paths in a single query.
        :param paths: Canonical config paths to look up.
        :return: Mapping of config_path to Vehicle, only containing vehicles that exist.
        """
        unique_paths = set(paths)
        if not unique_paths:
            return {}
        vehicles = self.db.query(self.model).filter(self.model.config_path.in_(unique_paths)).all()
        return {vehicle.config_path: vehicle for vehicle in vehicles}

    def upsert_by_config_path(self, incoming: Vehicle, commit: bool = True) -> Vehicle:
        """
        Upsert a vehicle keyed by its config_path.

        When a vehicle with the same config_path exists, only the columns explicitly
        set on ``incoming`` are copied onto it, so unset columns keep their stored value.
        :param incoming: A transient Vehicle holding the new data, including config_path.
        :param commit: Commit immediately, if False the row is only flushed.
        :return: The created or updated Vehicle.
        """
        existing = self.get_by_config_path(incoming.config_path)
        if existing:
            for key, value in inspect(incoming).dict.items():
                if key in self.model.__table__.columns and key != "id":
                    setattr(existing, key, value)
            vehicle = existing
        else:
            vehicle = incoming
            self.db.add(vehicle)

        if commit:
            self.db.commit()
            self.db.refresh(vehicle)
        else:
            self.db.flush()
        return vehicle

    def replace_configurations(
        self,
        vehicle: Vehicle,
        motors: list[dict],
        fill_units: list[dict],
        commit: bool = True,
    ) -> Vehicle:
        """
        Sync the motor and fill unit configurations of a vehicle, keyed by index.

        Existing rows are updated in place (so ids referenced by map_vehicles stay
        stable), new indexes are added, and only indexes that no longer exist are deleted.
        :param vehicle: The vehicle to update.
        :param motors: Kwargs for each VehicleMotorConfiguration (index, name, hp, ...).
        :param fill_units: Kwargs for each VehicleFillUnitConfiguration (index, name, ...).
        :param commit: Commit immediately, if False the changes are only flushed.
        :return: The updated vehicle.
        """
        self._sync(vehicle.motor_configurations, motors, VehicleMotorConfiguration)
        self._sync(vehicle.fill_unit_configurations, fill_units, VehicleFillUnitConfiguration)

        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return vehicle

    @staticmethod
    def _sync(existing: list, rows: list[dict], model: type) -> None:
        """
        Upsert rows into a configuration relationship collection by index.
        :param existing: The relationship collection of existing config rows.
        :param rows: Desired rows as kwargs, each containing an 'index'.
        :param model: The configuration model class used for new rows.
        """
        by_index = {row.index: row for row in existing}
        wanted = {row["index"] for row in rows}

        for row in rows:
            current = by_index.get(row["index"])
            if current is None:
                existing.append(model(**row))
                continue
            for key, value in row.items():
                setattr(current, key, value)

        for index, current in by_index.items():
            if index not in wanted:
                existing.remove(current)

    def filter(self, category: str | None = None, brand: str | None = None) -> list[Vehicle]:
        """
        Get vehicles, optionally filtered by category and/or brand.
        :param category: Category slug (e.g. "medium_tractors"), falling back to a
            label or raw shop category, e.g. "Medium Tractors" or "TRACTORSM",
            ignoring case.
        :param brand: Display brand, e.g. "John Deere".
        :return: Matching vehicles.
        """
        query = self.db.query(self.model)
        if category:
            known = VehicleCategory.from_slug(category)
            if known:
                query = query.filter(func.lower(self.model.category) == known.name.lower())
            else:
                query = query.filter(
                    or_(
                        func.lower(self.model.category_label) == category.lower(),
                        func.lower(self.model.category) == category.lower(),
                    )
                )
        if brand:
            query = query.filter(self.model.brand == brand)
        return query.all()
