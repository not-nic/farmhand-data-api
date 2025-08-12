"""
Pytest conftest.py module containing test setup, TestClient Fixtures and other mocks.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional, Any, Generator

import boto3
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from httpx import Request, Response
from moto import mock_aws
from mypy_boto3_s3.client import S3Client

from main import app
from src.api.core.config import settings
from src.api.core.db.db_setup import SessionLocal, engine
from src.api.core.db.models._model_base import SqlAlchemyBase
from src.api.core.schema.mods import ModDetailModel
from src.api.services.file_parser_service import ExtractedZip, FileParserService
from src.api.services.modhub_service import ModHubService
from tests.utils import load_test_resource


@pytest.fixture(scope="function")
def db():
    """
    Fixture providing a database session
    :return: database session fixture.
    """
    SqlAlchemyBase.metadata.drop_all(bind=engine)
    SqlAlchemyBase.metadata.create_all(bind=engine)

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


@pytest.fixture()
def mock_s3() -> Generator[tuple[S3Client, str], Any, None]:
    """
    Fixture that mocks a boto3 AWS S3 Client.
    """
    with mock_aws():
        client: S3Client = boto3.client("s3", region_name="eu-west-2")
        bucket_name: str = settings.AWS_S3_BUCKET_NAME

        client.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={"LocationConstraint": "eu-west-2"}
        )

        yield client, bucket_name


@pytest.fixture
def mock_mod_hub_page(mocker) -> callable:
    """
    Create a fixture for a ModHub page, define which HTML resource should be
    returned and what status code.
    :param mocker: Pytest mocker.
    :return: A callable _mock_page function.
    """

    def _mock_page(file_name: Optional[str] = None, status_code: int = status.HTTP_200_OK) -> None:
        html_content = load_test_resource(file_name) if file_name else ""
        request = Request(method="GET", url=settings.BASE_FS_URL)

        mock_response = Response(
            status_code=status_code,
            content=html_content,
            request=request,
        )

        async_mock = mocker.AsyncMock(return_value=mock_response)
        mocker.patch("httpx.AsyncClient.get", async_mock)

    return _mock_page


@pytest.fixture
def mod_detail():
    """
    Fixture containing a mod_detail used by the mocked ModHub service instance.
    :return: (ModDetailModel) containing a mocked Farming Sim mod.
    """
    return ModDetailModel(
        id=123456,
        name="Custom Map 1",
        Game="FS25",
        Manufacturer="Lizard",
        Category="European Maps",
        Author="user",
        Size="30 MB",
        Version="1.0.0.0",
        Released="30.04.2025",
        Platform="PC/MAC",
        file_url="https://mod-download.com/custom-map-1.zip",
        zip_filename="custom-map-1.zip"
    )


@pytest.fixture
def mock_mod_hub_service(mocker, mod_detail) -> ModHubService:
    """
    Fixture to mock an instance and methods of the ModHub service.
    :param mocker: Pytest-mocker instance.
    :param mod_detail: Mod detail fixture.
    :return: Mocked instance of the ModHub service.
    """
    mock_service = mocker.Mock(spec=ModHubService)

    mock_service.get_pages.return_value = [0]
    mock_service.scrape_mod.return_value = mod_detail
    mock_service.scrape_mods.return_value = []
    mock_service.download_mod.return_value = b"zip-file-contents"
    mock_service.get_download_url.return_value = f"{settings.BASE_FS_URL}/download/{mod_detail.zip_filename}"

    mocker.patch("src.api.services.modhub_service.ModHubService", new=mock_service)

    return mock_service


@pytest.fixture
def mock_file_parser_service(mocker) -> Generator[FileParserService, Any, None]:
    """
    Fixture containing a mocked file parser service and an expected directory format.
    :param mocker: Pytest-mocker instance.
    :return: Mocked instance of the FileParserService.
    """
    temp_dir = TemporaryDirectory()
    temp_path = Path(temp_dir.name)

    file_names = ["map.i3d", "vehicles.xml", "overview.dds", "infoLayer.grle"]

    mock_extracted = ExtractedZip(
        files=[temp_path / name for name in file_names],
        root_dir=temp_path,
        temp_dir=temp_dir
    )

    restructured_files = [
        temp_path / "map/map.i3d",
        temp_path / "config/vehicles.xml",
        temp_path / "assets/overview.dds",
        temp_path / "data/infoLayer.grle"
    ]

    for file_path in restructured_files:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("some text")

    mock_file_parser_service = mocker.Mock()
    mock_file_parser_service.extract_zip.return_value = mock_extracted
    mock_file_parser_service.restructure_files.return_value = restructured_files

    yield mock_file_parser_service

    temp_dir.cleanup()
