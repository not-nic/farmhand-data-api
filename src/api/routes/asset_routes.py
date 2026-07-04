"""
API Routes for resolving map asset URIs to pre-signed URLs.

Routes:
    GET /assets/resolve?uri= - Resolve an S3 URI to a pre-signed URL.
"""

from botocore.exceptions import ClientError
from fastapi import APIRouter, HTTPException, Query, status

from src.api.core.dependencies import SessionDep
from src.api.services.assets_service import AssetsService

router = APIRouter(prefix="/assets", tags=["Assets"])


@router.get("/resolve", status_code=status.HTTP_200_OK)
async def resolve_asset_uri(
        db: SessionDep,
        uri: str = Query(
            description="S3 URI of the asset e.g. s3://farmhand-assets/123/assets/icon.png"
        ),
) -> dict:
    """
    Resolve an S3 URI returned by an API Endpoint into a to a pre-signed URL that
    can be fetched directly by the client.
    :param uri: The S3 URI to resolve.
    :return: Time-limited pre-signed URL for the asset.
    """
    try:
        url = AssetsService(db).resolve_uri(uri)
        return {"url": url}
    except ClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resolve URI: {exc}",
        )
