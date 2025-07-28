"""
Module containing the config / settings for the Farmhand Data API.
"""

import os
from typing import Literal, Optional

from pydantic import PostgresDsn, computed_field
from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseSettingsConfig(BaseSettings):
    """
    Shared settings for both Default & Unit Test settings.
    """

    model_config = SettingsConfigDict(
        env_file="./.env",
        env_ignore_empty=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "Farmhand Data API"
    VERSION: str = "0.1"
    API_V1_STR: str = "/api/v1"
    LOG_FORMAT: str = (
        "[%(asctime)s] - [%(levelname)s] - %(filename)s::%(funcName)s::%(lineno)s - %(message)s"
    )

    BASE_FS_URL: str = "https://www.farming-simulator.com"
    BASE_MODS_URL: str = f"{BASE_FS_URL}/mods.php"
    BASE_MOD_URL: str = f"{BASE_FS_URL}/mod.php"

    TESTING: bool


class Settings(BaseSettingsConfig):
    """
    Default settings object for the application.
    """

    POSTGRES_HOST: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    ENVIRONMENT: Literal["development", "testing", "production"] = "development"
    TESTING: bool

    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str
    AWS_S3_BUCKET_NAME: str

    MINIO_ENDPOINT_URL: Optional[str] = None

    PARSER_FILTERS: str = os.path.join("config", "filters.yml")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def DATABASE_URL(self) -> PostgresDsn:
        return MultiHostUrl.build(
            scheme="postgresql",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )


class TestSettings(BaseSettingsConfig):
    """
    Settings configuration used in unit tests.
    """

    DATABASE_URL: str = "sqlite:///./instance/testdb.sqlite"
    TESTING: bool


# Use TestSettings if TESTING environment variable is set, otherwise default to Settings
# TODO UPDATE THIS TO USE ENVIRONMENT instead of TESTING.
settings = TestSettings() if os.getenv("TESTING", "").lower() == "true" else Settings()
