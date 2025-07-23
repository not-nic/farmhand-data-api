"""
Pytest conftest.py module containing test setup, TestClient Fixtures and other mocks.
"""

import httpx
import pytest

from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import status
from fastapi.testclient import TestClient

from main import app
from src.api.core.db.models._model_base import SqlAlchemyBase
from src.api.core.dependencies import SessionDep
from tests.utils import load_test_resource


# Testing database configuration
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./instance/testdb.sqlite"
test_engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="module")
def db():
    """
    Fixture to create database and tables
    """
    db = TestingSessionLocal()
    SqlAlchemyBase.metadata.create_all(bind=test_engine)
    yield db
    SqlAlchemyBase.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="session")
def inject_database_dep(db):
    """
    Injects / Overrides the get_db dependency to use SQLite when testing.
    :param db: the database fixture.
    """

    def _inject():
        yield db

    app.dependency_overrides[SessionDep] = _inject
    yield
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def client(inject_database_dep):
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
        html_content = load_test_resource(file_name) if file_name else None
        dummy_request = httpx.Request(method="GET", url="https://fake-url.com")

        mock_response = httpx.Response(
            status_code=status_code, content=html_content, request=dummy_request
        )

        mocker.patch("httpx.get", return_value=mock_response)

    return _mock_page
