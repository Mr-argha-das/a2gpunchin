from fastapi import APIRouter

from app.schemas.kiosk import KioskFaceEnrollRequest, KioskFacePunchRequest, KioskLoginRequest, KioskLoginResponse
from app.services.kiosk import KioskService

router = APIRouter()
service = KioskService()


@router.post("/login", response_model=KioskLoginResponse)
def kiosk_login(payload: KioskLoginRequest):
    branch = service.login(payload.branch_code, payload.kiosk_pin)
    return {
        "branch_id": str(branch.id),
        "branch_name": branch.branch_name,
        "company_id": branch.company_id,
        "tenant_id": branch.tenant_id,
    }


@router.post("/face-punch")
def face_punch(payload: KioskFacePunchRequest):
    return service.punch(payload.model_dump(exclude_none=True))


@router.post("/enroll-face")
def enroll_face(payload: KioskFaceEnrollRequest):
    return service.enroll_face(payload.model_dump(exclude_none=True))
