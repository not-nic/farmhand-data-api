"""
Python module containing a class for downloading Mods from the ModHub
and handling interaction with S3.
"""
from botocore.exceptions import ClientError
from httpx2 import HTTPError

from src.api.core.logger import logger
from src.api.services.aws_service import AwsService
from src.api.services.modhub_service import ModHubService


class MapDownloadService:
    """
    Python class to download mods from the ModHub and manage interaction
    with Archives and Map files within S3.
    """
    def __init__(
            self,
            mod_hub_service: ModHubService | None = None,
            aws_service: AwsService | None = None,
    ):
        self.mod_hub_service = mod_hub_service or ModHubService()
        self.aws_service = aws_service or AwsService()

    async def download_map(self, map_id: int, filename: str) -> str:
        """
        Downloads a map and uploads it to an S3 bucket.
        :param map_id: The ID of the map from the ModHub.
        :param filename: The desired filename for the uploaded map.
        :return: (str) The S3 URI of the uploaded map.
        """
        try:
            download_url = await self.mod_hub_service.get_download_url(mod_id=map_id)
            map_content = await self.mod_hub_service.download_mod(download_url)
            return self.aws_service.upload_object(map_content, map_id, filename)
        except ClientError:
            raise
        except HTTPError as exc:
            logger.error(
                "Failed scraping or downloading map %s from ModHub. Reason: %s", map_id, exc
            )
            raise
