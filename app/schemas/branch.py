from pydantic import BaseModel, Field


class BranchCreate(BaseModel):
    tenant_id: str | None = None
    company_id: str | None = None
    branch_name: str
    branch_code: str
    address: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    allowed_radius: float = Field(default=100, ge=10)
    kiosk_pin: str = "1234"
    branch_manager: str | None = None


class BranchUpdate(BaseModel):
    tenant_id: str | None = None
    company_id: str | None = None
    branch_name: str | None = None
    address: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    allowed_radius: float | None = Field(default=None, ge=10)
    kiosk_pin: str | None = None
    branch_manager: str | None = None
