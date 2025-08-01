"""
API Routes for Scraping Data from ModHub.

This module defines the API routes for manually triggering scraping operations.
It allows the 'Service User' to scrape data from the ModHub.

Routes:
    - GET /scrape/{id}: Manually trigger scraping of an individual mod by its mod_id.
    - GET /scrape/maps: Manually trigger scraping of all maps from the ModHub website.

Dependencies:
    - is_service_user: Ensures that the request is coming from a service user.
"""

from fastapi import APIRouter, status

from src.api.core.schema.mods import ModDetailModel
from src.api.services.modhub_service import ModHubService

router = APIRouter(prefix="/scraper", tags=["Scraper"])


@router.get("/mods/{id}", status_code=status.HTTP_202_ACCEPTED, response_model_by_alias=False)
async def scrape_mod(id: int) -> ModDetailModel:
    """
    Function to manually trigger scraping of an individual mod by its mod_id.
    :param id: the mod_id in the ModHub URL
    :return: (202) Accepted and a message that the scraping has been started in the background.
    """
    mod_hub_service = ModHubService()
    return await mod_hub_service.scrape_mod(id)

