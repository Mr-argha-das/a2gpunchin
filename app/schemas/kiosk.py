from pydantic import BaseModel, Field


class KioskLoginRequest(BaseModel):
    branch_code: str
    kiosk_pin: str


class KioskLoginResponse(BaseModel):
    branch_id: str
    branch_name: str
    company_id: str | None
    tenant_id: str


class KioskFacePunchRequest(BaseModel):
    branch_id: str
    kiosk_pin: str
    action: str = Field(default="auto", pattern="^(auto|punch_in|punch_out)$")
    face_embedding: list[float]
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    device_info: str | None = None
    browser_fingerprint: str | None = None


class KioskFaceEnrollRequest(BaseModel):
    branch_id: str
    kiosk_pin: str
    employee_code: str
    face_embedding: list[float]
