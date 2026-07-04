"""
Extracts versioned changelog entries from free-text map descriptions.
"""

import re
from dataclasses import dataclass, field

from src.api.core.schema.mods.mod_desc import ChangeLogModel

_VERSION_RE = re.compile(r"v?(\d+(?:\.\d+){1,4})")
_HEADER_KEYWORDS = ("changelog", "update")
_BULLET_PREFIXES = ("-", "•", "*")

_REQUIRES_SAVE_PATTERNS = (
    re.compile(r"new savegame is required", re.I),
    re.compile(r"a new save(?:game)? is required", re.I),
    re.compile(r"new save(?:game)? required", re.I),
    re.compile(r"save(?:game)? recommended", re.I),
)
_NO_SAVE_PATTERNS = (
    re.compile(r"does not require (?:a )?new save(?:game)?", re.I),
    re.compile(r"no new save(?:game)?(?:\s+is)? required", re.I),
    re.compile(r"not require.*save", re.I),
    re.compile(r"savegame is not required", re.I),
)


@dataclass
class ExtractedChangelogs:
    """
    Result of extracting changelog sections from a raw description.
    """

    description: str
    changelogs: list[ChangeLogModel] = field(default_factory=list)


class ChangelogExtractor:
    """
    Splits a raw description into a cleaned description with changelog
    sections removed and an ordered list of ChangeLogModel entries.
    """

    def extract(self, text: str) -> ExtractedChangelogs:
        """
        Extract changelog entries from a raw description.
        :param text: The raw English description from modDesc.xml.
        :return: ExtractedChangelogs containing the cleaned description
            and the changelog list.
        """
        lines = text.splitlines()
        header_indices = [i for i, line in enumerate(lines) if self._is_header(line)]

        if not header_indices:
            return ExtractedChangelogs(description=text.strip())

        clean_description = "\n".join(lines[: header_indices[0]]).strip()
        changelogs: list[ChangeLogModel] = []

        for i, start in enumerate(header_indices):
            end = header_indices[i + 1] if i + 1 < len(header_indices) else len(lines)
            block = lines[start:end]

            version = self._extract_version(block[0])
            if not version:
                continue

            notes = self._extract_notes(block[1:])
            requires_save = self._requires_new_savegame("\n".join(block))

            changelogs.append(
                ChangeLogModel(version=version, notes=notes, requires_new_savegame=requires_save)
            )

        return ExtractedChangelogs(description=clean_description, changelogs=changelogs)

    @staticmethod
    def _is_header(line: str) -> bool:
        """Return True if the line looks like a changelog section header."""
        lowered = line.strip("# ").lower()
        return any(lowered.startswith(kw) for kw in _HEADER_KEYWORDS)

    @staticmethod
    def _extract_version(header_line: str) -> str | None:
        """Pull the version number out of a header line, if present."""
        match = _VERSION_RE.search(header_line)
        return match.group(1) if match else None

    @staticmethod
    def _extract_notes(lines: list[str]) -> list[str]:
        """Return the non-empty note lines within a changelog block, bullets stripped."""
        notes = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            for prefix in _BULLET_PREFIXES:
                if stripped.startswith(prefix):
                    stripped = stripped[1:].strip()
                    break
            notes.append(stripped)
        return notes

    @staticmethod
    def _requires_new_savegame(block_text: str) -> bool | None:
        """
        Determine whether the block states a new savegame is required.
        Returns None if the topic is not mentioned at all.
        """
        if any(p.search(block_text) for p in _NO_SAVE_PATTERNS):
            return False
        if any(p.search(block_text) for p in _REQUIRES_SAVE_PATTERNS):
            return True
        return None
