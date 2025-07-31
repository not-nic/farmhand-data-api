from pathlib import Path
from typing import Union

import yaml
from pydantic import BaseModel


class AlwaysIncludeModel(BaseModel):
    overview: list[str]
    xml: list[str]
    grle_data: list[str]
    map: list[str]
    mod: list[str]

    def flatten(self) -> list[str]:
        """
        Flatten all pattern lists into a single list of globs.
        """
        return [pattern for group in self.model_dump().values() for pattern in group]


class ParserFilterModel(BaseModel):
    excluded_file_types: list[str]
    excluded_files: list[str]
    excluded_directories: list[str]
    excluded_globs: list[str]
    always_include: AlwaysIncludeModel


class FarmhandModel(BaseModel):
    parser_filters: ParserFilterModel
    extra_content: list[str]


class ConfigModel(BaseModel):
    farmhand: FarmhandModel

    @classmethod
    def from_yaml_file(cls, file_path: Union[str, Path]) -> "ConfigModel":
        """
        Load the configuration from a YAML file.
        :param file_path: Path to the YAML file
        :return: ConfigModel instance
        """
        with open(file_path) as f:
            data = yaml.safe_load(f)
        return cls(**data)
