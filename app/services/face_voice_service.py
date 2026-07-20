from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any, Literal

from fastapi import HTTPException

from app.models.attendance import Attendance
from app.models.employee import Employee
from app.models.voice_auth import EmployeeVoiceProfile, FaceVoiceChallenge
from app.services.attendence_service import AttendanceRecord, EmployeeFace, AttendanceService
from app.services.fast_voice_engine import FastVoiceEngine
from app.services.face_liveness_security import FaceLivenessResult


Action = Literal["auto", "punch_in", "punch_out"]


class FaceVoiceService:
    def __init__(self, face_service: AttendanceService, voice_engine: FastVoiceEngine) -> None:
        self.face_service = face_service
        self.voice_engine = voice_engine

    @staticmethod
    def _ensure_employee_assigned_to_branch(employee: Employee, branch) -> None:
        if not employee.branch_id or str(employee.branch_id.id) != str(branch.id):
            raise HTTPException(status_code=403, detail="Employee is kiosk branch me assigned nahi hai.")

    @staticmethod
    def _ensure_face_enrolled(employee: Employee) -> None:
        has_face_record = EmployeeFace.objects(employee_id=employee.employee_code).only("id").first() is not None
        if not has_face_record and not bool(getattr(employee, "face_enrolled", False)):
            raise HTTPException(status_code=400, detail="Pehle employee ka face enroll karo, phir voice enroll hoga.")

    def enroll_voice(
        self,
        employee_code: str,
        branch_id: str,
        kiosk_pin: str,
        recordings: list[bytes],
    ) -> dict[str, Any]:
        branch = self.face_service._kiosk_branch(branch_id, kiosk_pin)
        employee = self.face_service._employee_for_face_id(employee_code)
        employee = self.face_service._ensure_employee_allowed_at_branch(employee, branch)
        self._ensure_employee_assigned_to_branch(employee, branch)
        self._ensure_face_enrolled(employee)
        try:
            result = self.voice_engine.enroll(recordings)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        profile = EmployeeVoiceProfile.objects(employee_id=employee).first()
        if profile is None:
            profile = EmployeeVoiceProfile(employee_id=employee, employee_code=employee.employee_code)
        profile.employee_code = employee.employee_code
        profile.embedding = result["embedding"]
        profile.sample_count = result["sample_count"]
        profile.minimum_pair_score = result["minimum_pair_score"]
        profile.updated_at = datetime.utcnow()
        profile.save()
        return {
            "success": True,
            "employee_id": str(employee.id),
            "employee_code": employee.employee_code,
            "voice_enrolled": True,
            "sample_count": profile.sample_count,
            "minimum_pair_score": profile.minimum_pair_score,
            "quality": result["quality"],
        }

    @staticmethod
    def _random_digits() -> str:
        while True:
            digits = "".join(str(secrets.randbelow(6) + 1) for _ in range(6))
            if len(set(digits)) >= 3:
                return digits

    def _resolve_action(self, employee: Employee, action: Action) -> str:
        today = self.face_service.admin_attendance_service.local_date()
        attendance = Attendance.objects(
            employee_id=employee,
            attendance_date=today,
            is_active=True,
        ).first()
        if action == "auto":
            return "punch_out" if attendance and attendance.check_in_time and not attendance.check_out_time else "punch_in"
        return action

    def create_challenge(
        self,
        image_bytes: bytes,
        branch_id: str,
        kiosk_pin: str,
        action: Action = "auto",
        liveness_result: FaceLivenessResult | None = None,
    ) -> dict[str, Any]:
        branch = self.face_service._kiosk_branch(branch_id, kiosk_pin)
        try:
            match = self.face_service.face_engine.search_employee(image_bytes)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if not match.get("found"):
            raise HTTPException(status_code=404, detail=match.get("message", "Face match nahi hua"))

        employee_face = EmployeeFace.objects(employee_id=match["employee_id"]).only("employee_id").first()
        if employee_face is None:
            raise HTTPException(status_code=404, detail="Matched employee face record nahi mila")
        employee = self.face_service._employee_for_face_id(employee_face.employee_id)
        employee = self.face_service._ensure_employee_allowed_at_branch(employee, branch)
        self._ensure_employee_assigned_to_branch(employee, branch)
        profile = EmployeeVoiceProfile.objects(employee_id=employee).only("id").first()
        if profile is None:
            raise HTTPException(status_code=400, detail="Employee voice enrolled nahi hai")

        liveness = {"challenge": "face_match", "motion_score": 0.0}
        security_fields = liveness_result.to_attendance_fields() if liveness_result else {}
        punch_type = self._resolve_action(employee, action)
        now = datetime.utcnow()
        FaceVoiceChallenge.objects(employee_id=employee, used=False).update(
            set__used=True,
            set__used_at=now,
        )
        challenge = FaceVoiceChallenge(
            challenge_id=uuid.uuid4().hex,
            employee_id=employee,
            employee_code=employee.employee_code,
            branch_id=branch,
            punch_type=punch_type,
            digits=self._random_digits(),
            face_confidence=float(match["confidence"]),
            liveness_challenge=security_fields.get("challenge_type") or liveness["challenge"],
            liveness_motion_score=float(liveness["motion_score"]),
            face_score=security_fields.get("face_score"),
            liveness_score=security_fields.get("liveness_score"),
            reflection_score=security_fields.get("reflection_score"),
            recognition_score=security_fields.get("recognition_score"),
            confidence_score=security_fields.get("confidence_score"),
            challenge_result=security_fields.get("challenge_result"),
            color_sequence=security_fields.get("color_sequence"),
            processing_time=security_fields.get("processing_time"),
            expires_at=now + timedelta(seconds=30),
        ).save()
        response = {
            "success": True,
            "challenge_id": challenge.challenge_id,
            "digits": " ".join(challenge.digits),
            "digits_raw": challenge.digits,
            "expires_in_seconds": 30,
            "action": punch_type,
            "employee_id": str(employee.id),
            "employee_code": employee.employee_code,
            "employee_name": f"{employee.first_name} {employee.last_name}".strip(),
            "instruction": "Har digit ko alag-alag Hindi ya English mein bolo",
        }
        response.update(security_fields)
        return response

    def recognize_image(
        self,
        image_bytes: bytes,
        branch_id: str,
        kiosk_pin: str,
    ) -> tuple[dict[str, Any], Employee]:
        branch = self.face_service._kiosk_branch(branch_id, kiosk_pin)
        try:
            match = self.face_service.face_engine.search_employee(image_bytes)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if not match.get("found"):
            raise HTTPException(status_code=404, detail=match.get("message", "Face match nahi hua"))
        employee_face = EmployeeFace.objects(employee_id=match["employee_id"]).only("employee_id").first()
        if employee_face is None:
            raise HTTPException(status_code=404, detail="Matched employee face record nahi mila")
        employee = self.face_service._employee_for_face_id(employee_face.employee_id)
        employee = self.face_service._ensure_employee_allowed_at_branch(employee, branch)
        self._ensure_employee_assigned_to_branch(employee, branch)
        return match, employee

    def _get_open_challenge(self, challenge_id: str, branch_id: str, kiosk_pin: str) -> FaceVoiceChallenge:
        branch = self.face_service._kiosk_branch(branch_id, kiosk_pin)
        now = datetime.utcnow()
        challenge = FaceVoiceChallenge.objects(
            challenge_id=challenge_id,
            branch_id=branch,
            used=False,
            expires_at__gt=now,
        ).first()
        if challenge is None:
            raise HTTPException(status_code=400, detail="Challenge expired, invalid ya already used hai")
        return challenge

    @staticmethod
    def _consume_challenge(challenge: FaceVoiceChallenge) -> None:
        consumed = FaceVoiceChallenge.objects(
            id=challenge.id,
            used=False,
            expires_at__gt=datetime.utcnow(),
        ).modify(new=True, set__used=True, set__used_at=datetime.utcnow())
        if consumed is None:
            raise HTTPException(status_code=400, detail="Challenge expired, invalid ya already used hai")

    def verify_and_punch(
        self,
        challenge_id: str,
        branch_id: str,
        kiosk_pin: str,
        audio_bytes: bytes,
    ) -> dict[str, Any]:
        challenge = self._get_open_challenge(challenge_id, branch_id, kiosk_pin)
        employee = challenge.employee_id
        self._ensure_employee_assigned_to_branch(employee, challenge.branch_id)
        profile = EmployeeVoiceProfile.objects(employee_id=employee).first()
        if profile is None:
            raise HTTPException(status_code=400, detail="Employee voice profile nahi mila")
        try:
            voice = self.voice_engine.verify(profile.embedding, challenge.digits, audio_bytes)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not voice["verified"]:
            raise HTTPException(status_code=401, detail={"success": False, **voice})
        self._consume_challenge(challenge)
        security_fields = self._challenge_security_fields(challenge)
        attendance = self._commit_punch(employee, challenge.punch_type, challenge.face_confidence, security_fields)
        response = {
            "success": True,
            "employee_id": str(employee.id),
            "employee_code": employee.employee_code,
            "employee_name": f"{employee.first_name} {employee.last_name}".strip(),
            "action": challenge.punch_type,
            "attendance_id": str(attendance.id),
            "face_confidence": challenge.face_confidence,
            "speaker_score": voice["speaker_score"],
            "check_in_time": attendance.check_in_time.isoformat() if attendance.check_in_time else None,
            "check_out_time": attendance.check_out_time.isoformat() if attendance.check_out_time else None,
        }
        response.update(security_fields)
        return response

    def _challenge_security_fields(self, challenge: FaceVoiceChallenge) -> dict[str, Any]:
        return {
            "face_score": challenge.face_score,
            "liveness_score": challenge.liveness_score,
            "reflection_score": challenge.reflection_score,
            "recognition_score": challenge.recognition_score,
            "confidence_score": challenge.confidence_score,
            "challenge_type": challenge.liveness_challenge,
            "challenge_result": challenge.challenge_result,
            "color_sequence": list(challenge.color_sequence or []),
            "processing_time": challenge.processing_time,
        }

    def _commit_punch(
        self,
        employee: Employee,
        action: str,
        face_confidence: float,
        security_fields: dict[str, Any] | None = None,
    ) -> Attendance:
        admin_service = self.face_service.admin_attendance_service
        now = datetime.utcnow()
        admin_service.auto_punch_out_overdue_for_employee(employee, now)
        employee_face = EmployeeFace.objects(employee_id=employee.employee_code).only("employee_id", "name", "department").first()
        if employee_face is None:
            raise HTTPException(status_code=404, detail="Employee face profile nahi mila")
        open_record = AttendanceRecord.objects(
            employee_id=employee.employee_code,
            status="PUNCHED_IN",
        ).order_by("-punch_in").first()

        if action == "punch_in":
            if open_record is not None:
                raise HTTPException(status_code=400, detail="Employee already punched in hai")
            record = AttendanceRecord(
                employee_id=employee.employee_code,
                employee_name=employee_face.name,
                department=employee_face.department,
                punch_in=now,
                status="PUNCHED_IN",
                punch_in_confidence=face_confidence,
                updated_at=now,
            ).save()
            self.face_service._apply_security_fields(record, security_fields)
            record.save()
            attendance = self.face_service._sync_admin_attendance(
                employee_face,
                "PUNCH_IN",
                now,
                security_fields=security_fields,
            )
        else:
            if open_record is None:
                raise HTTPException(status_code=400, detail="Open punch-in nahi mila")
            open_record.punch_out = now
            open_record.duration_seconds = max(0, int((now - open_record.punch_in).total_seconds()))
            open_record.status = "PUNCHED_OUT"
            open_record.punch_out_confidence = face_confidence
            open_record.updated_at = now
            self.face_service._apply_security_fields(open_record, security_fields)
            open_record.save()
            record = open_record
            attendance = self.face_service._sync_admin_attendance(
                employee_face,
                "PUNCH_OUT",
                now,
                punch_in_time=open_record.punch_in,
                security_fields=security_fields,
            )
        if attendance is None:
            raise HTTPException(status_code=500, detail="Main attendance sync nahi hui")
        return attendance
