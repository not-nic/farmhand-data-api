"""
Entrypoint for starting the application.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, status, Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError

from src.api.core.config import settings
from src.api.core.db.db_setup import engine
from src.api.core.db.models._model_base import SqlAlchemyBase
from src.api.routes import api_router
from src.api.utils import format_pydantic_errors


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Functions that can be run on the startup and teardown
    of an application.
    :param app: the FastAPI application instance
    """
    SqlAlchemyBase.metadata.create_all(engine)
    yield  # Continue running the app


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
