"""
Handler for Farming Simulator modDesc.xml files.

Fetches, parses, and persists modDesc.xml data including the mod description,
map description, config file paths, icon and preview assets, and mod dependencies.
"""

from sqlalchemy.orm import Session

from src.api.constants import AssetType, EntityType
from src.api.core.db.models import Map
from src.api.core.db.models.mods import ChangeLog
from src.api.core.logger import logger
from src.api.core.repositories.dependency_repository import DependencyRepository
from src.api.core.repositories.mod_description_repository import ModDescriptionRepository
from src.api.core.schema.mods.mod_desc import ModDescModel
from src.api.handlers.xml.base_xml_handler import BaseXmlHandler
from src.api.parsers.xml.mod_desc_xml_parser import ModDescXmlParser
from src.api.services.assets_service import AssetsService
from src.api.services.aws.aws_service import AwsService


class ModDescHandler(BaseXmlHandler[ModDescModel]):
    """
    Processes modDesc.xml for a map.

    Persists the ModDescription record, creates ICON and PREVIEW assets,
    and associates required mod dependencies with the map.
    """

    def __init__(
        self,
        db: Session,
        aws_service: AwsService,
        assets_service: AssetsService,
    ) -> None:
        super().__init__(db, aws_service, assets_service)
        self.mod_description_repository = ModDescriptionRepository(db)
        self.dependency_repository = DependencyRepository(db)

    def process(self, map_obj: Map) -> None:
        """
        Get, parse, and persist modDesc.xml for the given map.
        Skips maps without a data_uri as their files are not yet extracted.
        :param map_obj: The map to process.
        """
        if not map_obj.data_uri:
            logger.warning(
                "[ModDesc-Handler]: Skipping '%s' (%d) — no data_uri.",
                map_obj.name,
                map_obj.id,
            )
            return

        logger.info("[ModDesc-Handler]: Processing '%s' (%d).", map_obj.name, map_obj.id)

        content = self._get(f"{map_obj.data_uri}/config/modDesc.xml")
        parsed: ModDescModel = ModDescXmlParser().parse(content)
        self._store(map_obj, parsed)

        logger.info("[ModDesc-Handler]: Completed '%s' (%d).", map_obj.name, map_obj.id)

    def _store(self, map_obj: Map, parsed: ModDescModel) -> None:
        """
        Persist all data extracted from modDesc.xml.
        Upserts the ModDescription, creates assets, and associates dependencies.
        :param map_obj: The parent map.
        :param parsed: The parsed ModDescModel.
        """
        config = parsed.map_config

        self.mod_description_repository.upsert(
            map_id=map_obj.id,
            title=parsed.title,
            description=parsed.description,
            map_description=config.description if config else None,
            config_filename=config.config_filename if config else None,
            vehicles_filename=config.vehicles_filename if config else None,
            placeables_filename=config.placeables_filename if config else None,
            items_filename=config.items_filename if config else None,
        )

        self._store_changelogs(map_obj, parsed)
        self._create_assets(map_obj, parsed)
        self._associate_dependencies(map_obj, parsed)

    @staticmethod
    def _store_changelogs(map_obj: Map, parsed: ModDescModel) -> None:
        """
        Replace the map's changelog entries with the freshly parsed set.
        The description text is always the source of truth, so old
        entries are cleared before the new ones are added.
        :param map_obj: The parent map.
        :param parsed: The parsed ModDescModel.
        """
        map_obj.changelogs.clear()
        for entry in parsed.changelogs:
            map_obj.changelogs.append(
                ChangeLog(
                    version=entry.version,
                    notes=entry.notes,
                    requires_new_savegame=entry.requires_new_savegame,
                )
            )

    def _create_assets(self, map_obj: Map, parsed: ModDescModel) -> None:
        """
        Create ICON and PREVIEW asset records from modDesc.xml filenames.
        :param map_obj: The parent map.
        :param parsed: The parsed ModDescModel.
        """
        if parsed.icon_filename:
            self.assets_service.create_asset(
                entity_id=map_obj.id,
                entity_type=EntityType.MAP,
                filename=parsed.icon_filename,
                asset_type=AssetType.ICON,
            )

        config = parsed.map_config
        if config and config.preview_filename:
            self.assets_service.create_asset(
                entity_id=map_obj.id,
                entity_type=EntityType.MAP,
                filename=config.preview_filename,
                asset_type=AssetType.PREVIEW,
            )

    def _associate_dependencies(self, map_obj: Map, parsed: ModDescModel) -> None:
        """
        Upsert required mod dependencies and associate them with the map.
        :param map_obj: The parent map.
        :param parsed: The parsed ModDescModel.
        """
        map_obj.dependencies = [
            self.dependency_repository.upsert(dep)
            for dep in parsed.dependencies
        ]
