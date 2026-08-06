# Farmhand Data API

This is the `farmhand-data-api` which is a Python backend API for ingesting data into the farmhand application.
It handles scraping mods from the ModHub, XML conversion and Map & Savegame data.

Access the data API here: https://data.farmhand.uk/api/v1/maps/

> [!NOTE]
> See the `farmhand-service` backend API here: https://github.com/not-nic/farmhand

## Install Guide
1. Clone this repository on your machine:
   ```bash
   git clone git@github.com:not-nic/farmhand-data-api.git
   cd farmhand-data-api
   ```
2. Create a `.env` file with the following development variables:
   ```plaintext
   POSTGRES_HOST=database
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=postgres
   POSTGRES_DB=farmhand-data
   
   TESTING=false

   LOG_LEVEL=INFO
   
   ENVIRONMENT=development
   
   AWS_ACCESS_KEY_ID=farmhand-minio-user
   AWS_SECRET_ACCESS_KEY=minio-password
   AWS_REGION=eu-west-2
   AWS_S3_INGEST_BUCKET_NAME=farmhand-map-ingest-bucket
   AWS_S3_ASSETS_BUCKET_NAME=farmhand-assets-bucket
   MINIO_PUBLIC_ENDPOINT_URL=http://localhost:9000
   MINIO_ENDPOINT_URL=http://minio:9000
   ```

3. Start the service with docker:
   ```bash
   docker compose up
   ```

## Local Development
1. [Install uv](https://docs.astral.sh/uv/getting-started/installation/) if you don't already have it:

2. use `uv` to create the venv and install dependencies:
   ```bash
   uv sync
   ```
3. Run commands through uv by prefixing commands with `uv`:
   ```bash
   uv run pytest
   ```
4. Or activate the created `.venv` by using the following command on macOS / Linux:
   ```bash
   source .venv/bin/activate
   ``` 
   Or if you are on Windows use:
   ```bash
   .venv\Scripts\activate
   ```
5. Build the application for docker development with the following command:
   ```bash
   docker compose up --build
   ```
6. Verify the application has started properly by checking the output:
   ```plaintext
    farmhand-api  |                                                  
    farmhand-api  | ______                   _                     _
    farmhand-api  | |  ___|                 | |                   | |
    farmhand-api  | | |_ __ _ _ __ _ __ ___ | |__   __ _ _ __   __| |
    farmhand-api  | |  _/ _` | '__| '_ ` _ \| '_ \ / _` | '_ \ / _` |
    farmhand-api  | | || (_| | |  | | | | | | | | | (_| | | | | (_| |
    farmhand-api  | \_| \__,_|_|  |_| |_| |_|_| |_|\__,_|_| |_|\__,_|
    farmhand-api  |
    farmhand-api  | =========== Farmhand Data API started ============
   ```
7. Visit the documentation for the application by going to:
   ```plaintext
   http://localhost:8001/docs
   ```

## Linting

Linting and formatting is handled with Ruff. This repository loosely follows the Black formatter and PEP8 style guide.

Run linting and formatting with the following commands:

```bash
ruff check
```

```bash
ruff format
```

## Tests

Running unit tests requires the application to be setup (see [Local Development](#local-development)).

Make sure the application is set up and then use the following command to run all tests:
```bash
pytest tests
```
or test individual files with:
```bash
pytest pytest tests/api/services/test_modhub_service.py::TestModHubService::test_scrape_mock_mod -s -vv 
```
> Note: you can also use -s for standard output (prints, log messages, etc.) or -vv to produce a very verbose output.

### Test Coverage

To check the test coverage of the repository use the following command:
```bash
pytest --cov src 
```
