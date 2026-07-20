from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
from fastapi import HTTPException, Request, status

from app.core.config import settings
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


@dataclass
class FaceLivenessResult:
    face_score: float
    liveness_score: float
    reflection_score: float
    recognition_score: float
    confidence_score: float
    challenge_type: str
    challenge_result: str
    color_sequence: list[str]
    processing_time: float
    failure_reason: str | None
    audit: dict[str, Any]

    @property
    def passed(self) -> bool:
        return self.failure_reason is None and self.confidence_score >= settings.face_liveness_low_confidence_threshold

    @property
    def low_confidence(self) -> bool:
        return self.passed and self.confidence_score < settings.face_liveness_success_threshold

    def to_attendance_fields(self) -> dict[str, Any]:
        fields = {
            "face_score": self.face_score,
            "liveness_score": self.liveness_score,
            "reflection_score": self.reflection_score,
            "recognition_score": self.recognition_score,
            "confidence_score": self.confidence_score,
            "challenge_type": self.challenge_type,
            "challenge_result": self.challenge_result,
            "color_sequence": self.color_sequence,
            "processing_time": self.processing_time,
            "security_audit": self.audit,
        }
        if self.audit.get("audit_image_path"):
            fields["selfie_path"] = self.audit["audit_image_path"]
        return fields


class FaceLivenessSecurityService:
    """Server-side liveness scorer for multi-frame face attendance attempts."""

    def config(self) -> dict[str, Any]:
        return {
            "challenge_types": settings.face_liveness_challenges,
            "challenge_count_min": 1,
            "challenge_count_max": 2,
            "colors": ["white", "red", "blue", "green"],
            "color_duration_ms": settings.face_liveness_color_duration_ms,
            "min_frames": settings.face_liveness_min_frames,
            "max_frames": settings.face_liveness_max_frames,
            "thresholds": {
                "success": settings.face_liveness_success_threshold,
                "low_confidence": settings.face_liveness_low_confidence_threshold,
                "reflection_delta": settings.face_liveness_min_reflection_delta,
            },
            "scoring": {
                "face_detection": settings.face_liveness_score_face_detection,
                "challenge_success": settings.face_liveness_score_challenge,
                "head_movement": settings.face_liveness_score_head_movement,
                "light_reflection": settings.face_liveness_score_reflection,
                "face_recognition": settings.face_liveness_score_recognition,
            },
        }

    def evaluate(
        self,
        frames: list[bytes],
        metadata_json: str | None,
        recognition_confidence: float,
        request: Request | None = None,
    ) -> FaceLivenessResult:
        started = time.perf_counter()
        metadata = self._parse_metadata(metadata_json)
        challenge_types = self._as_string_list(metadata.get("challenge_types") or metadata.get("challenge_type"))
        color_sequence = self._as_string_list(metadata.get("color_sequence"))
        frame_results = list(metadata.get("frames") or [])
        failure_reason = self._validate_metadata(challenge_types, color_sequence, frames, frame_results)

        face_score = float(settings.face_liveness_score_face_detection if not failure_reason else 0)
        challenge_score = self._challenge_score(challenge_types, metadata) if not failure_reason else 0.0
        head_score = self._head_score(challenge_types, metadata) if not failure_reason else 0.0
        reflection_score = self._reflection_score(frames, color_sequence) if not failure_reason else 0.0
        recognition_score = self._recognition_score(recognition_confidence)

        confidence = face_score + challenge_score + head_score + reflection_score + recognition_score
        if reflection_score <= 0 and not failure_reason:
            failure_reason = "Reflection check failed"
        if challenge_score <= 0 and not failure_reason:
            failure_reason = "Challenge not completed"
        if confidence < settings.face_liveness_low_confidence_threshold and not failure_reason:
            failure_reason = "Confidence below threshold"

        processing_time = round(time.perf_counter() - started, 3)
        audit = {
            "frame_count": len(frames),
            "client_frame_results": frame_results,
            "device_id": metadata.get("device_id"),
            "gps": metadata.get("gps"),
            "ip": self._request_ip(request),
            "recognition_confidence": recognition_confidence,
            "low_confidence": settings.face_liveness_low_confidence_threshold <= confidence < settings.face_liveness_success_threshold,
        }
        result = FaceLivenessResult(
            face_score=round(face_score, 2),
            liveness_score=round(challenge_score + head_score, 2),
            reflection_score=round(reflection_score, 2),
            recognition_score=round(recognition_score, 2),
            confidence_score=round(confidence, 2),
            challenge_type="+".join(challenge_types),
            challenge_result="passed" if failure_reason is None else "failed",
            color_sequence=color_sequence,
            processing_time=processing_time,
            failure_reason=failure_reason,
            audit=audit,
        )
        if failure_reason:
            self.log_failed_attempt(result, request=request)
        return result

    def log_failed_attempt(self, result: FaceLivenessResult, request: Request | None = None) -> None:
        try:
            AuditLog(
                tenant_id="security",
                module="attendance_security",
                action="failed_liveness_attempt",
                ip_address=self._request_ip(request),
                metadata={
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "device_id": result.audit.get("device_id"),
                    "ip": result.audit.get("ip"),
                    "gps": result.audit.get("gps"),
                    "failure_reason": result.failure_reason,
                    "confidence_score": result.confidence_score,
                    "challenge_type": result.challenge_type,
                    "color_sequence": result.color_sequence,
                },
            ).save()
        except Exception:
            logger.warning("Attendance security audit log save failed.", exc_info=True)

    def save_audit_image(self, image_bytes: bytes, prefix: str = "low-confidence") -> str | None:
        try:
            directory = Path("uploads") / "attendance_security"
            directory.mkdir(parents=True, exist_ok=True)
            filename = f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex}.jpg"
            path = directory / filename
            path.write_bytes(image_bytes)
            return str(path)
        except Exception:
            logger.warning("Attendance security audit image save failed.", exc_info=True)
            return None

    def _parse_metadata(self, metadata_json: str | None) -> dict[str, Any]:
        if not metadata_json:
            return {}
        try:
            value = json.loads(metadata_json)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid liveness metadata JSON") from exc
        if not isinstance(value, dict):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid liveness metadata")
        return value

    def _validate_metadata(
        self,
        challenge_types: list[str],
        color_sequence: list[str],
        frames: list[bytes],
        frame_results: list[Any],
    ) -> str | None:
        if len(frames) < settings.face_liveness_min_frames:
            return "Too few live frames"
        if len(frames) > settings.face_liveness_max_frames:
            return "Too many live frames"
        if not challenge_types:
            return "Missing challenge"
        allowed = set(settings.face_liveness_challenges)
        if any(challenge not in allowed for challenge in challenge_types):
            return "Unsupported challenge"
        if len(set(color_sequence)) < 3:
            return "Invalid color sequence"
        for item in frame_results:
            if not isinstance(item, dict):
                continue
            face_count = int(item.get("face_count") or 0)
            if face_count != 1:
                return "Exactly one face is required"
            if item.get("centered") is False:
                return "Face is not centered"
            if item.get("size_ok") is False:
                return "Face distance is not acceptable"
        return None

    def _challenge_score(self, challenge_types: list[str], metadata: dict[str, Any]) -> float:
        results = metadata.get("challenge_results") or {}
        if not isinstance(results, dict):
            return 0.0
        passed = sum(1 for challenge in challenge_types if results.get(challenge) is True)
        if not challenge_types:
            return 0.0
        return settings.face_liveness_score_challenge * (passed / len(challenge_types))

    def _head_score(self, challenge_types: list[str], metadata: dict[str, Any]) -> float:
        head_challenges = {"turn_left", "turn_right", "look_up", "look_down"}
        requested = [item for item in challenge_types if item in head_challenges]
        if not requested:
            return float(settings.face_liveness_score_head_movement)
        results = metadata.get("challenge_results") or {}
        if not isinstance(results, dict):
            return 0.0
        passed = sum(1 for challenge in requested if results.get(challenge) is True)
        return settings.face_liveness_score_head_movement * (passed / len(requested))

    def _recognition_score(self, confidence: float) -> float:
        normalized = max(0.0, min(float(confidence), 100.0)) / 100.0
        return settings.face_liveness_score_recognition * normalized

    def _reflection_score(self, frames: list[bytes], color_sequence: list[str]) -> float:
        if len(frames) < 2:
            return 0.0
        brightness = [self._face_region_brightness(frame) for frame in frames]
        deltas = [abs(brightness[index] - brightness[index - 1]) for index in range(1, len(brightness))]
        average_delta = float(np.mean(deltas)) if deltas else 0.0
        min_delta = max(0.0, settings.face_liveness_min_reflection_delta)
        if average_delta < min_delta:
            return 0.0
        ratio = min(1.0, average_delta / (min_delta * 2))
        return settings.face_liveness_score_reflection * ratio

    def _face_region_brightness(self, image_bytes: bytes) -> float:
        import cv2

        image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return 0.0
        height, width = image.shape[:2]
        # Approximate forehead, nose, and cheek band from the centered face region.
        top = int(height * 0.22)
        bottom = int(height * 0.68)
        left = int(width * 0.28)
        right = int(width * 0.72)
        region = image[top:bottom, left:right]
        if region.size == 0:
            return 0.0
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        return float(np.mean(hsv[:, :, 2]))

    def _as_string_list(self, value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [str(item) for item in value if str(item)]
        return []

    def _request_ip(self, request: Request | None) -> str | None:
        if request is None or request.client is None:
            return None
        return request.client.host
