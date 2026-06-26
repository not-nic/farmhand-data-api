"""
Python module containing the FileParserService and supporting dataclass.

These classes are used for parsing a save game, filtering out unsued files,
and restructuring data into a standardised format.
"""

import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZipFile

from src.api.core.config import settings
from src.api.core.logger import logger
from src.api.core.schema.config import ConfigModel, ParserFilterModel


@dataclass
class ExtractedZip:
    """
    A resulting zip, containing the filtered files, the root of the temp directory,
    and a reference to the TemporaryDirectory so that it can be cleaned up.
    """

    files: list[Path]
    root_dir: Path
    temp_dir: TemporaryDirectory


class FileParserService:
    """
    Python service to extract files from a Farming Simulator mod .zip archive and
    restructures them into a standardised farmhand directory layout.

    Filtering is based on an allowlist defined in config/application.yml; a file
    is kept on a glob pattern of if it lives under a known extra_context directory.

    Anything not explicitly wanted is discarded.
    """

    DIRECTORY_SCHEMA: dict[str, list[str]] = {
        "config": [".xml"],
        "assets": [".dds", ".png", ".jpg", ".jpeg"],
        "data": [".grle"],
        "map": [".i3d"],
    }

    FALLBACK_DIRECTORY = "unused"
    EXTRA_ASSET_DIRS: set = {"sounds", "textures", "models", "effects", "particles"}

    def __init__(
        self,
        filters: ParserFilterModel | None = None,
        parser_directory_schema: dict | None = None,
    ):
        self.config = ConfigModel.from_yaml_file(settings.APPLICATION_CONFIG)
        self.filters = filters or self.config.farmhand.parser_filters
        self.extra_content = self.config.farmhand.extra_content
        self.parser_directory_schema = parser_directory_schema or self.DIRECTORY_SCHEMA

        self._include_patterns: list[str] = self.filters.always_include.flatten()
        self._extra_content_lower: set[str] = {e.lower() for e in self.extra_content}
        self._excluded_files: set[str] = set(self.filters.excluded_files)

    def extract_zip(self, filename: str) -> ExtractedZip:
        """
        Extract a mod archive and return only the files that pass the allowlist.

        :param filename: Path to the .zip to extract.
        :raises FileNotFoundError: If the zip does not exist.
        :raises BadZipFile: If the file is not a valid zip archive.
        :raises PermissionError: If the file cannot be read.
        """
        temp_dir = TemporaryDirectory()
        root_dir = Path(temp_dir.name)

        try:
            with ZipFile(filename, "r") as zip_file:
                zip_file.extractall(root_dir)
        except (FileNotFoundError, BadZipFile, PermissionError) as exc:
            logger.warning("[File Parser]: Failed to open '%s': %s", filename, exc)
            temp_dir.cleanup()
            raise

        all_files = [f for f in root_dir.rglob("*") if f.is_file()]
        kept = [f for f in all_files if self._should_keep(f.relative_to(root_dir))]

        logger.debug(
            "[File Parser]: %d -> %d files kept after allowlist filter.",
            len(all_files),
            len(kept),
        )

        return ExtractedZip(files=kept, root_dir=root_dir, temp_dir=temp_dir)

    def restructure_files(self, files: list[Path], root_dir: Path) -> list[Path]:
        """
        Copy each kept file into the farmhand directory layout under the root_dir.
        Extra-Content files are preserved under an /extra root, with their sub-path
        maintained.

        :param files: Filtered files are returned by extract_zip.
        :param root_dir: Root of the extracted mod.
        :return: List of paths in their new restructured locations.
        """
        start_time = time.monotonic()
        self._create_target_directories(root_dir)
        moved: list[Path] = []

        for file in files:
            relative_path = file.relative_to(root_dir)
            target = self._extra_content_target(relative_path, root_dir) or (
                root_dir / self._schema_directory(file) / file.name
            )
            target.parent.mkdir(parents=True, exist_ok=True)

            if file.resolve() != target.resolve():
                shutil.copy2(file, target)

            moved.append(target)

        logger.debug(
            "[File Parser]: Restructured %d file(s) in %.2fs.",
            len(moved),
            time.monotonic() - start_time,
        )
        return moved

    def remove_unwanted_extras(self, files: list[Path], root_dir: Path) -> list[Path]:
        """
        Post-process the 'filtered' files and remove any /extras that has context
        which are not defined in the extra_context allowlist.

        Call this after restructure_files and before uploading to S3 to catch
        anything that slipped through (e.g. a directory in the zip that matched
        an old extra_content entry now removed from config).

        :param files: Restructured file paths from restructure_files.
        :param root_dir: Root directory used to compute relative paths.
        :return: Cleaned file list with unwanted extras removed.
        """
        kept: list = []
        removed: list = []
        for file in files:
            parts = file.relative_to(root_dir).parts
            if (
                len(parts) >= 2
                and parts[0] == "extra"
                and parts[1].lower() not in self._extra_content_lower
            ):
                removed.append(file)
            else:
                kept.append(file)

        if removed:
            logger.debug(
                "[File Parser]: Post-processing removed %d file(s) from unwanted extra directories.",
                len(removed),
            )

        return kept

    def filter_extra_content(self, files: list[Path], root_dir: Path) -> list[Path]:
        """
        Post-process the /extra directories file and keep only the primary XML file
        for each item and attempt to discard textures, sounds, meshes, and other assets.

        Example:
            extra/vehicles/claasAxion800/axion800.xml is attempted to be kept, Anything deeper
            (sounds/, subfolders) or anything without a non-XML extension is dropped.

        :param files: Restructured file list from restructure_files.
        :param root_dir: Root directory used to compute relative paths.
        :return: Cleaned file list.
        """
        kept, removed = [], []

        for file in files:
            relative = file.relative_to(root_dir)
            parts = relative.parts

            if parts[0] != "extra":
                kept.append(file)
                continue

            # Drop anything that isn't XML regardless of depth.
            if file.suffix.lower() != ".xml":
                removed.append(file)
                continue

            # Drop XMLs that live inside a known asset subfolder at any depth.
            # extra/vehicles/claas/Axion800/sounds/axion800.xml → "sounds" in parts → drop
            # extra/vehicles/claas/Axion800/axion800.xml → no asset dir in parts → keep
            if any(part.lower() in self.EXTRA_ASSET_DIRS for part in parts):
                removed.append(file)
            else:
                kept.append(file)

        if removed:
            logger.debug(
                "[File Parser]: Extra content filtered %d asset(s), kept %d XML(s).",
                len(removed),
                len(kept),
            )

        return kept

    def _should_keep(self, relative_path: Path) -> bool:
        """
        Allowlist check: keep the file if it matches an always_include pattern,
        is a map i3d by location, or lives under a known extra_content directory.
        """
        if relative_path.name in self._excluded_files:
            return False
        if any(relative_path.match(p) for p in self._include_patterns):
            return True
        if self._is_map_i3d(relative_path):
            return True
        parts_lower = [p.lower() for p in relative_path.parts]
        return any(ec in parts_lower for ec in self._extra_content_lower)

    def _schema_directory(self, file: Path) -> str:
        """Return the schema target directory for this file's extension."""
        ext = file.suffix.lower()
        for directory, extensions in self.parser_directory_schema.items():
            if ext in extensions:
                return directory
        return self.FALLBACK_DIRECTORY

    def _extra_content_target(self, relative_path: Path, root_dir: Path) -> Path | None:
        """
        If the file is under a known extra_content directory, return a target
        path under extra/ that preserves its sub-path. Otherwise, None.
        """
        parts_lower = [p.lower() for p in relative_path.parts]
        matched = next((ec for ec in self._extra_content_lower if ec in parts_lower), None)
        if matched:
            idx = parts_lower.index(matched)
            return root_dir / "extra" / Path(*relative_path.parts[idx:])
        return None

    def _create_target_directories(self, root_dir: Path) -> None:
        """
        Create the target directories within the TemporaryDirectory based on
        the provided parser_directory_schema.
        :param root_dir: The root of the TemporaryDirectory.
        """
        for directory in self.parser_directory_schema:
            (root_dir / directory).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _is_map_i3d(relative_path: Path) -> bool:
        """
        Detect map .i3d files that use the mod name instead of map.i3d, mapEU.i3d, etc.
        Example:
            maps/mechet.i3d
            maps/Hermannshausenmap.i3d
        :param relative_path: (Path) the path of the item to check.
        :return: (bool) if the map uses the mod name instead of map.i3d.
        """
        return (
                relative_path.suffix.lower() == ".i3d"
                and relative_path.parent.name.lower() == "maps"
        )
