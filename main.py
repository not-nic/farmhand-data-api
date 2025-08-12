"""
Entrypoint for starting the application.
"""

from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.api.core.config import settings
from src.api.routes import api_router
from src.api.tasks import base_scheduler
from src.api.utils import format_pydantic_errors

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Functions that can be run on the startup and teardown
    of an application.
    :param app: The FastAPI application instance
    """
    scheduler.start()
    base_scheduler.schedule_jobs(scheduler=scheduler)

    yield  # Continue running the app
    scheduler.shutdown()


app = FastAPI(title=f"{settings.PROJECT_NAME}-{settings.VERSION}", lifespan=lifespan)
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Exception handler for pydantic validation errors to return a standard format:
        '{"detail": "error message"}'
    :param request: FastAPI Request object
    :param exc: the pydantic validation error
    :return: a new JSON response of a formatted pydantic error.
    """
    error = format_pydantic_errors(exc)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=jsonable_encoder(error)
    )
