"""
API Routes for resolving map asset URIs to pre-signed URLs.

Routes:
    GET /assets/resolve?uri= - Resolve an S3 URI to a pre-signed URL.
"""
from datetime import UTC, datetime, timedelta

from botocore.exceptions import ClientError
from fastapi import APIRouter, HTTPException, Query, status

from src.api.core.dependencies import SessionDep
from src.api.core.schema.assets import ResolvedAssetResponse
from src.api.services.assets.assets_service import AssetsService

router = APIRouter(prefix="/assets", tags=["Assets"])


@router.get("/resolve", status_code=status.HTTP_200_OK)
async def resolve_asset_uri(
        db: SessionDep,
        uri: str = Query(
            description="S3 URI of the asset e.g. s3://farmhand-assets/123/assets/icon.png"
        ),
) -> ResolvedAssetResponse:
    """
    Resolve an S3 URI returned by an API Endpoint into a to a pre-signed URL that
    can be fetched directly by the client.
    :param db: Database Session Dependency.
    :param uri: The S3 URI to resolve.
    :return: Time-limited pre-signed URL for the asset.
    """
    expiry_time: int = 3600

    try:
        url = AssetsService(db).resolve_uri(uri, expiry_time)
        return ResolvedAssetResponse(
            url=url,
            expires_at=datetime.now(UTC) + timedelta(seconds=expiry_time))
    except ClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resolve URI: {exc}",
        )
