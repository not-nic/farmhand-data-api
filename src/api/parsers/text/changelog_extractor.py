"""
Extracts versioned changelog entries from free-text map descriptions.
"""

import re
from dataclasses import dataclass, field

from src.api.core.schema.mods.mod_desc import ChangeLogModel


@dataclass
class ExtractedChangelogs:
    """
    Result of extracting changelog sections from a raw description.
    """

    description: str
    changelogs: list[ChangeLogModel] = field(default_factory=list)


class ChangelogExtractor:
    """
    Class to a description from the ModHub into a 'cleaned description' and
    an extracted change log.
    """

    VERSION_REGEX = re.compile(r"v?(\d+(?:\.\d+){1,4})")
    HEADERS = ("changelog", "update")
    LIST_PREFIX = ("-", "•", "*")

    REQUIRES_NEW_SAVE = (
        re.compile(r"new savegame is required", re.I),
        re.compile(r"a new save(?:game)? is required", re.I),
        re.compile(r"new save(?:game)? required", re.I),
        re.compile(r"save(?:game)? recommended", re.I),
    )
    NO_NEW_SAVE = (
        re.compile(r"does not require (?:a )?new save(?:game)?", re.I),
        re.compile(r"no new save(?:game)?(?:\s+is)? required", re.I),
        re.compile(r"not require.*save", re.I),
        re.compile(r"savegame is not required", re.I),
    )

    def extract(self, text: str) -> ExtractedChangelogs:
        """
        Extract changelog entries from a raw description.
        :param text: The raw English description from modDesc.xml.
        :return: ExtractedChangelogs containing the cleaned description and the changelog list.
        """
        lines = text.splitlines()
        header_indices = [
            line_no for line_no, line in enumerate(lines) if self._is_header(line)
        ]

        if not header_indices:
            return ExtractedChangelogs(description=text.strip())

        clean_description = "\n".join(lines[: header_indices[0]]).strip()
        changelogs: list[ChangeLogModel] = []

        boundaries = [*header_indices, len(lines)]

        for start, end in zip(boundaries, boundaries[1:], strict=True):
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

    def _is_header(self, line: str) -> bool:
        """
        Extract a 'changelog' section header from a body of text.
        :param line: The line to check.
        :return: (bool) If the line looks like a changelog section header.
        """
        lowered = line.strip("# ").lower()
        return any(lowered.startswith(kw) for kw in self.HEADERS)

    def _extract_version(self, header_line: str) -> str | None:
        """
        Get the version number out of a changelog header line, if present.
        :param header_line: The header line to check.
        :return: (str | None) a version number.
        """
        match = self.VERSION_REGEX.search(header_line)
        return match.group(1) if match else None

    def _extract_notes(self, lines: list[str]) -> list[str]:
        """
        Extract change log note lines within a 'changelog' free-text block,
        removing the bullet points.
        :param lines: The lines to extract from.
        :return: (list) A list of stripped lines.
        """
        notes = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            for prefix in self.LIST_PREFIX:
                if stripped.startswith(prefix):
                    stripped = stripped[1:].strip()
                    break
            notes.append(stripped)
        return notes

    def _requires_new_savegame(self, block_text: str) -> bool | None:
        """
        Best guess to determine whether the text block requires a new savegame.
        :param block_text: The next block to check.
        :return: (Optional(bool)) Returns None if the topic is not mentioned at all.
        """
        if any(p.search(block_text) for p in self.NO_NEW_SAVE):
            return False
        if any(p.search(block_text) for p in self.REQUIRES_NEW_SAVE):
            return True
        return None
