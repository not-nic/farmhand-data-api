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


@dataclass(frozen=True)
class ContentOverride:
    """
    A dataclass defining the new file location of a file in a Farming
    Simulator Mod, e.g. '/foliage -> extra/crops/... and a boolean
    to check whether only its primary XML file should be kept.
    """

    target: str
    xml_only: bool = False


class FileParserService:
    """
    Python service to extract files from a Farming Simulator mod .zip archive and
    restructures them into a standardised farmhand directory layout.

    Filtering is based on an allowlist defined in config/application.yml; a file
    is kept on a glob pattern of if it lives under a known extra_content directory.

    Anything not explicitly wanted is discarded.
    """

    DIRECTORY_SCHEMA: dict[str, list[str]] = {
        "config": [".xml"],
        "assets": [".dds", ".png", ".jpg", ".jpeg"],
        "data": [".grle"],
        "map": [".i3d"],
    }

    FALLBACK_DIRECTORY = "unused"
    ASSET_SUBDIRECTORY_NAMES: set[str] = {"sounds", "textures", "models", "effects", "particles"}
    CONTENT_OVERRIDES: dict[str, ContentOverride] = {
        "foliage": ContentOverride(target="extra/crops", xml_only=True),
    }

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
        self._xml_only_names_lower: set[str] = {
            name.lower()
            for name, override in self.CONTENT_OVERRIDES.items()
            if override.xml_only
        }

    def process(self, filename: str) -> ExtractedZip:
        """
        Process a Farming Simulator Mod Map into a restructured directory.

        :param filename: Path to the .zip to extract.
        :return: ExtractedZip with the final, filtered set of files.
        :raises FileNotFoundError: If the zip does not exist.
        :raises BadZipFile: If the file is not a valid zip archive.
        :raises PermissionError: If the file cannot be read.
        """
        extracted = self.extract_zip(filename)
        files = self.restructure_files(extracted.files, extracted.root_dir)
        files = self.remove_unwanted_extras(files, extracted.root_dir)
        files = self.filter_extra_content(files, extracted.root_dir)

        return ExtractedZip(files=files, root_dir=extracted.root_dir, temp_dir=extracted.temp_dir)

    def extract_zip(self, filename: str) -> ExtractedZip:
        """
        Extract a mod archive and return only the files that pass the allowlist.

        :param filename: (str) Path to the .zip to extract.
        :return: (ExtractedZIp) the extracted zip dataclass containing the files, root and
        temp directory.
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
        Copy each kept file into the farmhand directory layout under root_dir.

        :param files: (list) Filtered files that are returned by extract_zip.
        :param root_dir: (Path) Root of the extracted mod.
        :return: (list) List of paths in their new restructured locations.
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
        Remove any extra/ content whose directory is no longer in extra_content.

        :param files: (list) Restructured file paths from restructure_files.
        :param root_dir: (Path) Root directory used to compute relative paths.
        :return: (list) Cleaned file list with unwanted extras removed.
        """
        special_extra_roots = {
            override.target.split("/", 1)[1].split("/")[0]
            for override in self.CONTENT_OVERRIDES.values()
            if override.target.startswith("extra/")
        }

        kept: list = []
        removed: list = []
        for file in files:
            parts = file.relative_to(root_dir).parts
            if (
                len(parts) >= 2
                and parts[0] == "extra"
                and parts[1] not in special_extra_roots
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
        Reduce extra/ content down to the primary XML file per item.

        :param files: (list) Restructured file list from restructure_files.
        :param root_dir: (Path) Root directory used to compute relative paths.
        :return: (list) Cleaned file list.
        """
        xml_only_roots = {
            override.target.split("/")[-1]
            for override in self.CONTENT_OVERRIDES.values()
            if override.xml_only
        }

        kept, removed = [], []

        for file in files:
            relative = file.relative_to(root_dir)
            parts = relative.parts

            if parts[0] != "extra":
                kept.append(file)
                continue

            if len(parts) >= 2 and parts[1] in xml_only_roots:
                if file.suffix.lower() == ".xml":
                    kept.append(file)
                else:
                    removed.append(file)
                continue

            if file.suffix.lower() != ".xml":
                removed.append(file)
                continue

            if any(part.lower() in self.ASSET_SUBDIRECTORY_NAMES for part in parts):
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
        Check if a file should be kept or removed.

        :param relative_path: (Path) The path of the file.
        :return: (bool) if the file should be kept or excluded.
        """
        if relative_path.name in self._excluded_files:
            return False
        if any(relative_path.match(p) for p in self._include_patterns):
            return True
        if self._uses_map_naming_convention(relative_path, ".i3d"):
            return True
        if self._uses_map_naming_convention(relative_path, ".xml"):
            return True

        parts_lower = [p.lower() for p in relative_path.parts]

        if any(name in parts_lower for name in self._xml_only_names_lower):
            return relative_path.suffix.lower() == ".xml"

        return any(ec in parts_lower for ec in self._extra_content_lower)

    def _schema_directory(self, file: Path) -> str:
        """
        Return the schema target directory for this file's extension.

        :param file: (Path) The file to move.
        :return: (str) the directory this file should be moved to.
        """
        ext = file.suffix.lower()
        for directory, extensions in self.parser_directory_schema.items():
            if ext in extensions:
                return directory
        return self.FALLBACK_DIRECTORY

    def _extra_content_target(self, relative_path: Path, root_dir: Path) -> Path | None:
        """
        Get the restructured target path for a known extra_content file.

        :param relative_path: (Path) The relative path of the file.
        :param root_dir: (Path) The root directory of the mod.
        :return: (Path) The new path of the extra content relative to the /extras directory.
        """
        parts_lower = [p.lower() for p in relative_path.parts]
        matched = next((ec for ec in self._extra_content_lower if ec in parts_lower), None)

        if not matched:
            return None

        override = self.CONTENT_OVERRIDES.get(matched)
        if override:
            return root_dir / override.target / relative_path.name

        idx = parts_lower.index(matched)
        return root_dir / "extra" / Path(*relative_path.parts[idx:])

    def _create_target_directories(self, root_dir: Path) -> None:
        """
        Create the target directories within the TemporaryDirectory based on
        the provided parser_directory_schema.

        :param root_dir: (Path) The root of the TemporaryDirectory.
        """
        for directory in self.parser_directory_schema:
            (root_dir / directory).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _uses_map_naming_convention(relative_path: Path, suffix: str) -> bool:
        """
        Match a file against the map's own naming convention for the given
        extension.

        :param relative_path: (Path) the path of the item to check.
        :return: (bool) if this is the map's own config XML file.
        """
        if relative_path.suffix.lower() != suffix:
            return False

        parts = relative_path.parts
        if len(parts) == 1:
            return True
        if len(parts) == 2:
            return parts[0].lower() == "maps"
        if len(parts) == 3 and parts[0].lower() == "maps":
            return parts[1].lower() == relative_path.stem.lower()

        return False
