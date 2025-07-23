"""
Module containing the config / settings for the Farmhand Data API.
"""

from typing import Literal

from pydantic import computed_field, PostgresDsn
from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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

    POSTGRES_HOST: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    ENVIRONMENT: Literal["development", "testing", "production"] = "development"

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

    BASE_MODS_URL: str = "https://www.farming-simulator.com/mods.php"
    BASE_MOD_URL: str = "https://www.farming-simulator.com/mod.php"


settings = Settings()
