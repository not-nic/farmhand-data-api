"""
Module containing unit tests for the GET /vehicles/categories route,
including that it does not collide with GET /vehicles/{id}.
"""

from fastapi import status
from fastapi.testclient import TestClient

from src.api.constants import VehicleCategory
from src.api.core.config import settings
from src.api.core.db.models import Vehicle


class TestGetVehicleCategories:
    """
    Tests for GET /vehicles/categories.
    """

    CATEGORIES_URL = f"{settings.API_V1_STR}/vehicles/categories"
    VEHICLES_URL = f"{settings.API_V1_STR}/vehicles"

    def test_returns_sorted_category_slugs_and_labels(self, client: TestClient):
        """
        Every category should be returned as {slug, label}, sorted by label,
        without needing any vehicles ingested.
        """
        response = client.get(self.CATEGORIES_URL)

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        expected = sorted(
            (
                {"slug": category.slug, "label": category.value}
                for category in VehicleCategory
            ),
            key=lambda category: category["label"],
        )
        assert body == expected
        assert {"slug": "medium_tractors", "label": "Medium Tractors"} in body

    def test_category_slug_is_usable_as_filter(self, client: TestClient, db):
        """
        A returned slug should work directly as the 'category' query param on GET /vehicles,
        filtering on the raw key it maps to.
        """
        category = next(iter(VehicleCategory))
        db.add(
            Vehicle(
                config_path="vehicles/a.xml", name="a", category=category.name,
                category_label=category.value,
            )
        )
        db.add(
            Vehicle(
                config_path="vehicles/b.xml", name="b", category="OTHERCATEGORY",
                category_label="Other Category",
            )
        )
        db.commit()

        categories = client.get(self.CATEGORIES_URL).json()
        assert {"slug": category.slug, "label": category.value} in categories

        filtered = client.get(self.VEHICLES_URL, params={"category": category.slug})
        assert filtered.status_code == status.HTTP_200_OK
        vehicles = filtered.json()["vehicles"]
        assert len(vehicles) == 1
        assert vehicles[0]["name"] == "a"
