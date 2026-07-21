"""
Handler for Farming Simulator modDesc.xml files.

Fetches, parses, and persists modDesc.xml data including the mod description,
map description, config file paths, icon and preview assets, and mod dependencies.
"""

from sqlalchemy.orm import Session

from src.api.constants import AssetType, EntityType
from src.api.core.config import settings
from src.api.core.db.models import Map
from src.api.core.db.models.mods import ChangeLog
from src.api.core.logger import logger
from src.api.core.repositories.dependency_repository import DependencyRepository
from src.api.core.repositories.mod_description_repository import ModDescriptionRepository
from src.api.core.schema.mods.mod_desc import MapConfigModel, ModDescModel
from src.api.handlers.xml.base_xml_handler import BaseXmlHandler
from src.api.parsers.xml.mod_desc_xml_parser import ModDescXmlParser
from src.api.services.assets.assets_service import AssetsService
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
        Persist all data extracted from modDesc.xml, upserts the ModDescription,
        assets, and associates dependencies.

        :param map_obj: The parent map.
        :param parsed: The parsed ModDescModel.
        """
        config = parsed.map_config or MapConfigModel()

        self.mod_description_repository.upsert(
            map_id=map_obj.id,
            title=parsed.title,
            description=parsed.description,
            map_description=config.description,
            config_filename=config.config_filename,
            vehicles_filename=config.vehicles_filename,
            placeables_filename=config.placeables_filename,
            items_filename=config.items_filename,
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
        Register ICON and PREVIEW asset metadata from modDesc.xml filenames.

        :param map_obj: The parent map.
        :param parsed: The parsed ModDescModel.
        """
        if parsed.icon_filename:
            self._register_asset(map_obj, parsed.icon_filename, AssetType.ICON)

        config = parsed.map_config or MapConfigModel()
        if config.preview_filename:
            self._register_asset(map_obj, config.preview_filename, AssetType.PREVIEW)

    def _register_asset(self, map_obj: Map, filename: str, asset_type: AssetType) -> None:
        """
        Build the converted asset's target URI and register it against the map.

        :param map_obj: The parent map.
        :param filename: The original .dds filename from modDesc.xml.
        :param asset_type: The type of asset (icon, preview, etc.).
        """
        converted_filename = self.assets_service.image_converter.convert_filename(
            filename, self.assets_service.OUTPUT_FORMAT
        )
        asset_uri = self.assets_service.build_asset_uri(
            map_obj.id, converted_filename, settings.AWS_S3_ASSETS_BUCKET_NAME
        )

        self.assets_service.register_asset(
            entity_id=map_obj.id,
            entity_type=EntityType.MAP,
            asset_type=asset_type,
            filename=filename,
            asset_uri=asset_uri,
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
