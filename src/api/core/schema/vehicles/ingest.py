"""
Pydantic model for the result of a vehicle catalogue ingest.
"""

from pydantic import BaseModel


class VehicleIngestResult(BaseModel):
    """
    Summary of a vehicle catalogue ingest.

    Attributes:
        store_items: Number of in-scope vehicles found in the store items file.
        vehicles_upserted: Number of vehicles created or updated.
        with_configurations: Number of vehicles that had parsed vehicle XML data.
        xml_failures: Number of vehicle XML files that failed to parse and were skipped.
        assets_registered: Number of vehicle store images registered for conversion.
    """

    store_items: int
    vehicles_upserted: int
    with_configurations: int
    xml_failures: int
    assets_registered: int = 0
