from datetime import datetime

import pytest

from src.api.core.schema.mods import ModDetailModel


class TestModModel:
    def test_validate_release_date_creates_date(self):
        """
        Test that when the pydantic validator is given the correct date
        format it returns the value as a date.
        """
        date_string = "12.03.2025"
        result = ModDetailModel.validate_release_date(date_string)
        assert result == datetime(2025, 3, 12).date()

    def test_validate_release_date_uses_date(self):
        """
        Test that when the pydantic validator is given the correct date
        format it returns the value as a date.
        """
        date_string = datetime(2025, 3, 12).date()
        result = ModDetailModel.validate_release_date(date_string)
        assert result == date_string

    def test_validate_release_date_failure(self):
        """
        test that when the pydantic validator is given the wrong
        date format it raises a validation error.
        """
        invalid_date_string = "2025-03-12"
        with pytest.raises(
            ValueError,
            match=f"Invalid date format: {invalid_date_string}. Expected format is 'dd.mm.yyyy'.",
        ):
            ModDetailModel.validate_release_date(invalid_date_string)

    def test_platforms_are_split_into_list(self):
        """
        test that when given a string of platforms they are split into
        individual keys.
        """
        result = ModDetailModel.validate_platform("PC/MAC, XBS, PS5")
        assert result == ["PC/MAC", "XBS", "PS5"]
