import logging
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.services.face_voice_service import FaceVoiceService


router = APIRouter(prefix="/api/v1/face-voice", tags=["Face + Voice Attendance"])
service: FaceVoiceService | None = None
logger = logging.getLogger(__name__)

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
AUDIO_TYPES = {
    "audio/wav", "audio/x-wav", "audio/webm", "audio/ogg", "audio/mpeg",
    "audio/mp4", "video/webm", "application/octet-stream",
}


def set_face_voice_service(value: FaceVoiceService) -> None:
    global service
    service = value


def get_service() -> FaceVoiceService:
    if service is None:
        raise RuntimeError("FaceVoiceService initialize nahi hui")
    return service


async def read_file(file: UploadFile, allowed: set[str], max_bytes: int) -> bytes:
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")
    data = await file.read()
    if not data or len(data) > max_bytes:
        raise HTTPException(status_code=400, detail="File empty ya allowed size se badi hai")
    return data


@router.post("/enroll")
async def enroll_voice(
    employee_code: Annotated[str, Form(...)],
    branch_id: Annotated[str, Form(...)],
    kiosk_pin: Annotated[str, Form(...)],
    samples: Annotated[list[UploadFile], File(...)],
):
    if not 5 <= len(samples) <= 8:
        raise HTTPException(status_code=400, detail="Exactly 5 se 8 voice samples bhejo")
    try:
        recordings = [await read_file(item, AUDIO_TYPES, 8 * 1024 * 1024) for item in samples]
        return get_service().enroll_voice(employee_code, branch_id, kiosk_pin, recordings)
    except HTTPException as exc:
        logger.warning("Voice enrollment failed for %s: %s", employee_code, exc.detail)
        raise


@router.post("/challenge")
async def face_voice_challenge(
    image: Annotated[UploadFile, File(...)],
    branch_id: Annotated[str, Form(...)],
    kiosk_pin: Annotated[str, Form(...)],
    action: Annotated[Literal["auto", "punch_in", "punch_out"], Form()] = "auto",
):
    image_bytes = await read_file(image, IMAGE_TYPES, 10 * 1024 * 1024)
    return get_service().create_challenge(
        image_bytes,
        branch_id,
        kiosk_pin,
        action,
    )


@router.post("/verify")
async def verify_voice_and_punch(
    challenge_id: Annotated[str, Form(...)],
    branch_id: Annotated[str, Form(...)],
    kiosk_pin: Annotated[str, Form(...)],
    audio: Annotated[UploadFile, File(...)],
):
    audio_bytes = await read_file(audio, AUDIO_TYPES, 8 * 1024 * 1024)
    return get_service().verify_and_punch(challenge_id, branch_id, kiosk_pin, audio_bytes)


@router.get("/health")
def face_voice_health():
    value = get_service()
    return {"status": "ok", "voice_model_loaded": value.voice_engine.is_ready}
