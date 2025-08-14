"""
Module for the FastAPI routes and the routers
each set of routes should be appended too.
"""

from fastapi import APIRouter

from src.api.routes import data_routes, map_routes, scrape_routes

api_router = APIRouter()
api_router.include_router(scrape_routes.router)
api_router.include_router(map_routes.router)
api_router.include_router(data_routes.router)
