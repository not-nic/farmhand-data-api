"""
Pytest conftest.py module containing test setup, TestClient Fixtures and other mocks.
"""

from typing import Optional

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from httpx import Request, Response

from main import app
from src.api.core.db.db_setup import get_engine, engine, SessionLocal
from src.api.core.db.models._model_base import SqlAlchemyBase
from src.api.core.dependencies import SessionDep
from tests.utils import load_test_resource


@pytest.fixture(scope="module")
def create_database():
    """
    Fixture to create database and tables
    """
    SqlAlchemyBase.metadata.create_all(bind=engine)
    yield
    SqlAlchemyBase.metadata.drop_all(bind=engine)


@pytest.fixture(scope="module")
def db(create_database):
    """
    Fixture providing a database session
    :return: database session fixture.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session")
def client(db):
    """
    Fixture for a FastAPI test client
    """
    return TestClient(app)


@pytest.fixture
def mock_mod_hub_page(mocker) -> callable:
    """
    Create a fixture for a modhub page, define which HTML resource should be
    returned and what status code.
    :param mocker: pytest mocker
    :return: a callable _mock_page function
    """

    def _mock_page(file_name: Optional[str] = None, status_code: int = status.HTTP_200_OK) -> None:
        html_content = load_test_resource(file_name) if file_name else ""
        request = Request(method="GET", url="https://farmhand-unit-test.uk")

        mock_response = Response(
            status_code=status_code,
            content=html_content,
            request=request,
        )

        # Patch the async method
        async_mock = mocker.AsyncMock(return_value=mock_response)
        mocker.patch("httpx.AsyncClient.get", async_mock)

    return _mock_page
