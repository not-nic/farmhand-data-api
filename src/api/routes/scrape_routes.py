"""
API Routes for Scraping Data from ModHub.

This module defines the API routes for manually triggering scraping operations.
It allows the 'Service User' to scrape data from the ModHub.

Routes:
    - GET /scrape/{id}: Manually trigger scraping of an individual mod by its mod_id.
    - GET /scrape/maps: Manually trigger scraping of all maps from the ModHub website.

"""

from fastapi import APIRouter, HTTPException, status

from src.api.core.dependencies import SessionDep
from src.api.core.schema.mods import ModDetailModel
from src.api.services.map_service import MapService
from src.api.services.modhub_service import ModHubService

router = APIRouter(prefix="/scraper", tags=["Scraper"])


@router.get("/maps")
async def get_maps(db: SessionDep) -> dict:
    """
    Get new maps from the Farming Simulator ModHub, store them in a bucket
    and parse the required files.
    """
    map_service = MapService(db)
    try:
        await map_service.get_new_maps()
    except Exception as exc:
        raise HTTPException(
            detail=str(exc),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return {"message": "Successfully scraped and downloaded new maps from the ModHub."}


@router.get("/mods/{mod_id}", status_code=status.HTTP_200_OK, response_model_by_alias=False)
async def scrape_mod(mod_id: int) -> ModDetailModel:
    """
    Function to manually trigger scraping of an individual mod by its mod_id.
    :param mod_id: The mod_id in the ModHub URL.
    :return: Scraped information of the requested mod_id.
    """
    mod_hub_service = ModHubService()
    return await mod_hub_service.scrape_mod(mod_id)

