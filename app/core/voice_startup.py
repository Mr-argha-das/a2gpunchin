"""Call initialize_voice() during FastAPI startup/lifespan."""

import os
from typing import Callable

import torch

from app.services.voice_attendance_service import DigitTranscriber, VoiceAttendanceService
from app.services.voice_engine import VoiceEngine
from app.routes.voice_attendance import set_voice_attendance_service
from app.services.spectra_antispoof import SpectraAASISTDetector


def initialize_voice(
    authorize: Callable[[str, str, str], None] | None = None,
) -> VoiceAttendanceService:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    production = os.getenv("APP_ENV", "development").lower() == "production"
    if production and authorize is None:
        raise RuntimeError("Production me employee/branch/kiosk authorization callback required hai.")
    authorization = authorize or (lambda employee_id, branch_id, kiosk_pin: None)
    anti_spoof_dir = os.getenv("SPECTRA_AASIST_DIR")
    if production and not anti_spoof_dir:
        raise RuntimeError("Production me SPECTRA_AASIST_DIR required hai.")
    anti_spoof = SpectraAASISTDetector(anti_spoof_dir, device) if anti_spoof_dir else None
    engine = VoiceEngine(
        data_dir=os.getenv("VOICE_DATA_DIR", "./data/voice"),
        speaker_threshold=float(os.getenv("VOICE_SPEAKER_THRESHOLD", "0.72")),
        spoof_threshold=float(os.getenv("VOICE_SPOOF_THRESHOLD", "0.80")),
        device=device,
        anti_spoof=anti_spoof,
        require_anti_spoof=production,
    )
    engine.initialize()
    transcriber = DigitTranscriber(
        model_name=os.getenv("WHISPER_MODEL", "small"),
        device=device,
    )
    service = VoiceAttendanceService(engine, transcriber, authorization)
    set_voice_attendance_service(service)
    return service


