from datetime import date

from pydantic import BaseModel


class AssetCreate(BaseModel):
    employee_id: str
    asset_id: str
    asset_type: str
    asset_name: str
    brand_model: str | None = None
    serial_number: str | None = None
    sim_number: str | None = None
    assigned_on: date | None = None
    returned_on: date | None = None
    status: str = "assigned"
    condition: str | None = None
    note: str | None = None


class AssetUpdate(BaseModel):
    employee_id: str | None = None
    asset_id: str | None = None
    asset_type: str | None = None
    asset_name: str | None = None
    brand_model: str | None = None
    serial_number: str | None = None
    sim_number: str | None = None
    assigned_on: date | None = None
    returned_on: date | None = None
    status: str | None = None
    condition: str | None = None
    note: str | None = None
