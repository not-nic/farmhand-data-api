"""
Python module containing the FileParserService and supporting Dataclass.

These classes are used for parsing a save game, filtering out unsued files
and restructuring data into a standardised format.
"""

import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional
from zipfile import BadZipFile, ZipFile

from src.api.core.config import settings
from src.api.core.logger import logger
from src.api.core.schema.config import ConfigModel, ParserFilterModel


@dataclass
class ExtractedZip:
    """
    Extracted Zip dataclass containing files, root directory
    and the temporary directory this has been stored in.
    """
    files: list[Path]
    root_dir: Path
    temp_dir: TemporaryDirectory


class FileParserService:
    """
    File Parser Service class used for parsing files from a Farming Simulator Mod File.

    Extracts all files from an FS .zip file, reformats the directory and filters out
    any unused files.
    """

    def __init__(
            self,
            filters: Optional[ParserFilterModel] = None,
            parser_directory_schema: Optional[dict] = None
    ):
        """
        Constructor for the FileParserService.
        :param filters: (FilterModel) .yaml configuration for filtering out files from a Mod.
        :param parser_directory_schema: (dict) for the restructured directory.
        """
        self.config = ConfigModel.from_yaml_file(settings.APPLICATION_CONFIG)
        self.filters = filters or self.config.farmhand.parser_filters
        self.extra_content = self.config.farmhand.extra_content

        self.parser_directory_schema = parser_directory_schema or {
            "config": [".xml"],
            "assets": [".dds", ".png", ".jpg", ".jpeg"],
            "data": [".grle"],
            "map": [".i3d"],
            "unused": set()
        }

    def extract_zip(self, filename: str) -> ExtractedZip:
        """
        Function to extract and filter out files from a Farming Simulator Mod.
        :param filename: the .zip file to extract (e.g. FS25_mod.zip)
        :return: (ExtractedZip) of the filtered files, root directory and temporary directory
        files are stored in.
        """

        temp_dir = TemporaryDirectory()
        root_dir = Path(temp_dir.name)

        try:
            with ZipFile(filename, "r") as zip_file:
                zip_file.extractall(root_dir)
        except FileNotFoundError:
            logger.warning(f"[File Parser]: ZIP with file {filename} not found...")
            temp_dir.cleanup()
            raise
        except BadZipFile:
            logger.warning(f"[File Parser]: File '{filename}' is not a valid ZIP archive.")
            temp_dir.cleanup()
            raise
        except PermissionError:
            logger.warning(f"[File Parser]: Permission denied when accessing '{filename}'.")
            temp_dir.cleanup()
            raise

        all_files = [f for f in root_dir.rglob("*") if f.is_file()]

        if not all_files:
            logger.warning("[File Parser]: ZIP file is empty or contains no valid files.")

        logger.info(f"[File Parser]: Extracted {len(all_files)} files from {root_dir}")

        filtered_files = self.apply_filters(all_files, root_dir)

        logger.info(f"[File Parser]: Based on filters '{len(filtered_files)}' files are valid.")

        return ExtractedZip(files=filtered_files, root_dir=root_dir, temp_dir=temp_dir)

    def restructure_files(self, files: list[Path], root_dir: Path) -> list[Path]:
        """
        Function to restructure the directory of extracted files into a 'farmhand'
        format for data validation.
        :param files: extracted or all files from a Farming Simulator Mod .zip.
        :param root_dir: the root directory of the extracted files.
        :return: (list) of the restructured directory.
        """
        start_time = time.monotonic()
        logger.info("[File Parser]: Starting file restructuring for %d files", len(files))

        self._create_target_directories(self.parser_directory_schema, root_dir)
        moved_files = []

        for file in files:
            relative_path = file.relative_to(root_dir)

            matched_dir = self.__get_matching_directory(file)
            target = self.__handle_extra_content(relative_path, root_dir)

            if not target:
                target = root_dir / matched_dir / file.name
                logger.debug("[File Parser]: Default file moving to '%s': %s", matched_dir, target)

            target.parent.mkdir(parents=True, exist_ok=True)
            logger.debug("[File Parser]: Moving '%s' -> '%s'", file, target)

            if file.resolve() != target.resolve():
                shutil.copy2(file, target)
            else:
                logger.debug(
                    "[File Parser]: Skipping move for '%s' as source and target are the same",
                    file
                )

            moved_files.append(target)

        duration = time.monotonic() - start_time
        logger.info(
            "[File Parser]: Restructured %d files in %.2f seconds",
            len(moved_files),
            duration
        )

        return moved_files

    def apply_filters(self, files: list[Path], root_dir: Path) -> list[Path]:
        """
        Apply filters to extracted files.
        :param files: extracted files
        :param root_dir: root path to compute relative paths
        """
        filtered_files = []
        for file in files:
            if self.__do_filter(file, root_dir):
                logger.debug("Keeping file: %s", file.name)
                filtered_files.append(file)
            else:
                logger.debug("Filtering out file: %s", file)

        return filtered_files

    def __get_matching_directory(self, file: Path) -> str:
        """
        Determine the matched directory based on the parser schema.
        :param file: Path object of the file.
        :return: Directory name where the file should be moved.
        """
        file_extension = file.suffix.lower()
        for directory, extensions in self.parser_directory_schema.items():
            if file_extension in extensions:
                return directory
        return "unused"

    def __handle_extra_content(self, relative_path: Path, root_dir: Path) -> Optional[Path]:
        """
        Determines if a file belongs to extra content and returns then returns the 'extras' target
        path.
        :param relative_path: path relative to root_dir.
        :param root_dir: root of the extracted mod files.
        :return: target path under 'extra' folder if matched, else None.
        """
        relative_parts = [part.lower() for part in relative_path.parts]
        extra_content = [item.lower() for item in self.extra_content]

        extras_folder = next((folder for folder in extra_content if folder in relative_parts), None)

        if extras_folder:
            folder_index = relative_parts.index(extras_folder)
            original_folder_name = relative_path.parts[folder_index]
            trimmed_path = Path(*relative_path.parts[folder_index:])
            target = root_dir / "extra" / trimmed_path

            logger.debug(
                "[File Parser]: Found '%s' extra content preserving file path: %s",
                original_folder_name,
                trimmed_path
            )
            return target

        return None

    @staticmethod
    def _create_target_directories(target_directory_schema: dict, root_dir: Path) -> None:
        """
        Create target directories based on the directory schema.
        :param root_dir: (path) the root directory of the 'Mod' for these files to be
        created at.
        """
        logger.info(f"Creating new directory structure for: {root_dir.name}")
        for directory in target_directory_schema:
            path = root_dir / directory
            path.mkdir(parents=True, exist_ok=True)

    def __do_filter(self, file: Path, root_dir: Path) -> bool:
        """
        Private method to filter a file, checking all filters specified in the
        yaml configuration.
        :param file: (Path) the file to check.
        :param root_dir: (path) the root directory to apply filters form.
        :return: (bool) if the file should be filtered or not.
        """
        relative_path = file.relative_to(root_dir)
        return (
            self.__always_include_filter(relative_path) or not (
                self.__exclude_glob_filter(relative_path) or
                self.__exclude_file_type_filter(file) or
                self.__exclude_file_filter(file) or
                self.__exclude_directory_filter(file)
            )
        )

    def __always_include_filter(self, file_path: Path) -> bool:
        """
        Private method for the always include filter, to always include in the final
        output.
        :param file_path: the file_path to check.
        :return: (bool) if the file should be filtered or not.
        """
        return any(file_path.match(pattern) for pattern in self.filters.always_include.flatten())

    def __exclude_glob_filter(self, file_path: Path) -> bool:
        """
        Private method for the 'glob' filter to filter out certain directory files
        .e.g. "textures/*.dds".
        :param file_path: the file_path to check.
        :return: (bool) if the file should be filtered or not.
        """
        return any(file_path.match(pattern) for pattern in self.filters.excluded_globs)

    def __exclude_file_type_filter(self, file: Path) -> bool:
        """
        Private method for the file type filter to filter files based on
        file type.
        :param file: the file_path to check.
        :return: (bool) if the file should be filtered or not.
        """
        return file.suffix in self.filters.excluded_file_types

    def __exclude_file_filter(self, file: Path) -> bool:
        """
        Private method to exclude files based on their name or path.
        :param file: the file_path to check.
        :return: (bool) if the file should be filtered or not.
        """
        return file.name in self.filters.excluded_files

    def __exclude_directory_filter(self, file: Path) -> bool:
        """
        Private method for the directory filter to filter out unused or unneeded directories.
        :param file: the file_path to check.
        :return: (bool) if the file should be filtered or not.
        """
        return any(ex_dir in file.parts for ex_dir in self.filters.excluded_directories)

