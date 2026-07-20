from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
from fastapi import HTTPException
from mongoengine import (
    BinaryField,
    DateTimeField,
    DictField,
    Document,
    FloatField,
    IntField,
    ListField,
    StringField,
)

from app.core.config import settings
from app.models.attendance import Attendance
from app.models.branch import Branch
from app.models.employee import Employee
from app.models.face_engine import FaceEngine
from app.services.attendance import AttendanceService as AdminAttendanceService


class EmployeeFace(Document):
    employee_id = StringField(required=True, unique=True)
    name = StringField(required=True)
    department = StringField()
    image = BinaryField(required=True)
    image_content_type = StringField(default="image/jpeg")
    faiss_id = IntField(required=True)
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    meta = {
        "collection": "employee_faces",
        "indexes": ["employee_id", "faiss_id"],
    }


class AttendanceRecord(Document):
    employee_id = StringField(required=True)
    employee_name = StringField(required=True)
    department = StringField()
    punch_in = DateTimeField(required=True)
    punch_out = DateTimeField()
    duration_seconds = IntField()
    status = StringField(required=True, choices=("PUNCHED_IN", "PUNCHED_OUT"))
    punch_in_confidence = FloatField()
    punch_out_confidence = FloatField()
    face_score = FloatField()
    liveness_score = FloatField()
    reflection_score = FloatField()
    recognition_score = FloatField()
    confidence_score = FloatField()
    challenge_type = StringField()
    challenge_result = StringField()
    color_sequence = ListField(StringField())
    processing_time = FloatField()
    security_audit = DictField()
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)

    meta = {
        "collection": "attendance_records",
        "indexes": ["employee_id", "status", "-punch_in"],
    }


class AttendanceService:
    def __init__(self, face_engine: FaceEngine) -> None:
        self.face_engine = face_engine
        self.admin_attendance_service = AdminAttendanceService()

    def _employee_for_face_id(self, employee_id: str) -> Employee | None:
        employee_id = employee_id.strip()
        employee = Employee.objects(employee_code=employee_id, is_active=True).first()
        if employee:
            return employee
        try:
            return Employee.objects(id=employee_id, is_active=True).first()
        except Exception:
            return None

    def _employee_name(self, employee: Employee | None, fallback: str) -> str:
        if not employee:
            return fallback.strip()
        return f"{employee.first_name} {employee.last_name}".strip() or fallback.strip()

    def _employee_department(self, employee: Employee | None, fallback: str | None) -> str | None:
        if employee and employee.department_id:
            return employee.department_id.department_name
        return fallback.strip() if fallback else None

    def _kiosk_branch(self, branch_id: str, kiosk_pin: str) -> Branch:
        branch = Branch.objects(id=branch_id, kiosk_pin=kiosk_pin, is_active=True).first()
        if not branch:
            raise HTTPException(status_code=401, detail="Invalid kiosk session")
        return branch

    def _ensure_employee_allowed_at_branch(self, employee: Employee | None, branch: Branch) -> Employee:
        if not employee:
            raise HTTPException(status_code=404, detail="Matched employee profile nahi mila.")
        if not employee.is_active or employee.status != "active":
            raise HTTPException(status_code=400, detail="Matched employee active nahi hai.")
        if employee.tenant_id != branch.tenant_id:
            raise HTTPException(status_code=403, detail="Employee is kiosk branch ke tenant me nahi hai.")
        if branch.company_id and employee.company_id != branch.company_id:
            raise HTTPException(status_code=403, detail="Employee is kiosk company me nahi hai.")
        return employee

    def _image_motion_score(self, first_image_bytes: bytes, second_image_bytes: bytes) -> float:
        import cv2

        first = self.face_engine._decode_image(first_image_bytes)
        second = self.face_engine._decode_image(second_image_bytes)
        first_gray = cv2.cvtColor(first, cv2.COLOR_BGR2GRAY)
        second_gray = cv2.cvtColor(second, cv2.COLOR_BGR2GRAY)
        first_small = cv2.resize(first_gray, (96, 96), interpolation=cv2.INTER_AREA)
        second_small = cv2.resize(second_gray, (96, 96), interpolation=cv2.INTER_AREA)
        return float(np.mean(cv2.absdiff(first_small, second_small)))

    def _verify_liveness(
        self,
        image_bytes: bytes,
        liveness_image_bytes: bytes,
        liveness_challenge: str,
        expected_employee_id: str,
    ) -> dict[str, Any]:
        allowed_challenges = {"blink", "turn_left", "turn_right", "look_up"}
        if liveness_challenge not in allowed_challenges:
            raise HTTPException(status_code=400, detail="Invalid liveness challenge.")

        motion_score = self._image_motion_score(image_bytes, liveness_image_bytes)
        min_motion_score = max(0.0, getattr(settings, "face_liveness_min_frame_delta", 3.5))
        if motion_score < min_motion_score:
            raise HTTPException(
                status_code=400,
                detail="Live movement detect nahi hua. Photo/screen ke bajay real face se dobara try karo.",
            )

        liveness_match = self.face_engine.search_employee(liveness_image_bytes)
        if not liveness_match["found"]:
            raise HTTPException(status_code=400, detail="Liveness frame me face reliably match nahi hua.")
        if liveness_match["employee_id"] != expected_employee_id:
            raise HTTPException(status_code=400, detail="Liveness frame same employee ka nahi hai.")

        return {"challenge": liveness_challenge, "motion_score": round(motion_score, 2)}

    def _sync_employee_enrollment(self, employee: Employee | None) -> None:
        if not employee:
            return
        employee.face_enrolled = True
        employee.save()

    def _sync_admin_attendance(
        self,
        employee_face: EmployeeFace,
        action: str,
        punch_time: datetime,
        punch_in_time: datetime | None = None,
        security_fields: dict[str, Any] | None = None,
    ) -> Attendance | None:
        employee = self._employee_for_face_id(employee_face.employee_id)
        if not employee or not employee.branch_id:
            return None

        check_in_at = punch_in_time or punch_time
        local_date = self.admin_attendance_service.to_local(check_in_at).date()
        open_attendance = (
            Attendance.objects(
                employee_id=employee,
                check_in_time__ne=None,
                check_out_time=None,
                is_active=True,
            )
            .order_by("-check_in_time")
            .first()
        )

        matching_attendance = Attendance.objects(
            employee_id=employee,
            attendance_date=local_date,
            check_in_time__ne=None,
            is_active=True,
        ).order_by("-check_in_time").first()

        if action == "PUNCH_IN":
            if open_attendance:
                return open_attendance
            if matching_attendance:
                return matching_attendance
            attendance = Attendance(
                tenant_id=employee.tenant_id,
                company_id=employee.company_id,
                employee_id=employee,
                branch_id=employee.branch_id,
                shift_id=employee.shift_id,
                attendance_date=local_date,
                check_in_time=check_in_at,
                latitude=employee.branch_id.latitude,
                longitude=employee.branch_id.longitude,
                distance_from_office=0,
                device_info="face-attendance-api",
                attendance_status="approved",
                check_in_status=self.admin_attendance_service._check_in_status(employee.shift_id, check_in_at)
                if employee.shift_id
                else "pending",
            )
            self._apply_security_fields(attendance, security_fields)
            self.admin_attendance_service.recalculate_attendance_status(attendance, save=False)
            attendance.save()
            return attendance

        attendance = open_attendance or matching_attendance
        if not attendance:
            attendance = Attendance(
                tenant_id=employee.tenant_id,
                company_id=employee.company_id,
                employee_id=employee,
                branch_id=employee.branch_id,
                shift_id=employee.shift_id,
                attendance_date=local_date,
                check_in_time=check_in_at,
                latitude=employee.branch_id.latitude,
                longitude=employee.branch_id.longitude,
                distance_from_office=0,
                device_info="face-attendance-api",
                attendance_status="approved",
                check_in_status=self.admin_attendance_service._check_in_status(employee.shift_id, check_in_at)
                if employee.shift_id
                else "pending",
            )
        attendance.check_out_time = punch_time
        attendance.latitude = employee.branch_id.latitude
        attendance.longitude = employee.branch_id.longitude
        attendance.distance_from_office = 0
        attendance.device_info = "face-attendance-api"
        if attendance.check_in_time:
            attendance.total_work_minutes = max(
                0,
                int(
                    (
                        self.admin_attendance_service._aware(punch_time)
                        - self.admin_attendance_service._aware(attendance.check_in_time)
                    ).total_seconds()
                    // 60
                ),
            )
        attendance.check_out_status = (
            self.admin_attendance_service._check_out_status(employee.shift_id, punch_time)
            if employee.shift_id
            else "normal"
        )
        self._apply_security_fields(attendance, security_fields)
        self.admin_attendance_service.recalculate_attendance_status(attendance, save=False)
        attendance.save()
        return attendance

    def _apply_security_fields(self, target: Any, security_fields: dict[str, Any] | None) -> None:
        if not security_fields:
            return
        for field, value in security_fields.items():
            if field in getattr(target, "_fields", {}):
                setattr(target, field, value)

    def register_employee(
        self,
        employee_id: str,
        name: str,
        branch_id: str,
        kiosk_pin: str,
        image_bytes: bytes,
        image_content_type: str,
        department: str | None = None,
    ) -> dict[str, Any]:
        branch = self._kiosk_branch(branch_id, kiosk_pin)
        employee_id = employee_id.strip()
        admin_employee = self._employee_for_face_id(employee_id)
        admin_employee = self._ensure_employee_allowed_at_branch(admin_employee, branch)
        face_employee_id = admin_employee.employee_code if admin_employee else employee_id
        employee_name = self._employee_name(admin_employee, name)
        employee_department = self._employee_department(admin_employee, department)

        try:
            face_result = self.face_engine.add_employee_face(face_employee_id, image_bytes)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if not face_result["success"]:
            raise HTTPException(status_code=400, detail=face_result["message"])

        employee = EmployeeFace.objects(employee_id=face_employee_id).first() or EmployeeFace(employee_id=face_employee_id)
        employee.name = employee_name
        employee.department = employee_department
        employee.image = image_bytes
        employee.image_content_type = image_content_type
        employee.faiss_id = face_result["faiss_id"]
        employee.updated_at = datetime.utcnow()
        employee.save()
        self._sync_employee_enrollment(admin_employee)

        return {
            "success": True,
            "message": "Employee image MongoDB me saved aur face FAISS me indexed.",
            "employee_id": employee.employee_id,
            "employee_code": employee.employee_id,
            "name": employee.name,
            "employee_name": employee.name,
            "department": employee.department,
            "image_saved": True,
            "faiss_id": employee.faiss_id,
        }

    def search_employees(
        self,
        branch_id: str,
        kiosk_pin: str,
        search: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        branch = Branch.objects(id=branch_id, kiosk_pin=kiosk_pin, is_active=True).first()
        if not branch:
            raise HTTPException(status_code=401, detail="Invalid kiosk session")

        query = Employee.objects(
            tenant_id=branch.tenant_id,
            company_id=branch.company_id,
            is_active=True,
            status="active",
        )
        search = search.strip() if search else None
        if search:
            from mongoengine import Q

            query = query.filter(
                Q(employee_code__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(email__icontains=search)
                | Q(phone__icontains=search)
            )

        results = []
        for employee in query.order_by("employee_code").limit(max(1, min(limit, 500))):
            department = employee.department_id
            results.append(
                {
                    "employee_id": str(employee.id),
                    "employee_code": employee.employee_code,
                    "employee_name": f"{employee.first_name} {employee.last_name}".strip(),
                    "department": department.department_name if department else None,
                    "face_enrolled": bool(employee.face_enrolled),
                }
            )
        return results

    def recognize_and_punch(
        self,
        image_bytes: bytes,
        branch_id: str,
        kiosk_pin: str,
        liveness_image_bytes: bytes,
        liveness_challenge: str,
        security_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        branch = self._kiosk_branch(branch_id, kiosk_pin)
        try:
            match = self.face_engine.search_employee(image_bytes)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if not match["found"]:
            return {
                "success": False,
                "recognized": False,
                "message": match["message"],
                "confidence": match.get("confidence"),
            }

        employee = EmployeeFace.objects(employee_id=match["employee_id"]).first()
        if employee is None:
            raise HTTPException(status_code=404, detail="Employee MongoDB me nahi mila.")
        self._ensure_employee_allowed_at_branch(self._employee_for_face_id(employee.employee_id), branch)
        try:
            liveness = self._verify_liveness(
                image_bytes,
                liveness_image_bytes,
                liveness_challenge,
                expected_employee_id=employee.employee_id,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        now = datetime.utcnow()
        self.admin_attendance_service.auto_punch_out_overdue(now)
        open_record = (
            AttendanceRecord.objects(employee_id=employee.employee_id, status="PUNCHED_IN")
            .order_by("-punch_in")
            .first()
        )

        if open_record is None:
            record = AttendanceRecord(
                employee_id=employee.employee_id,
                employee_name=employee.name,
                department=employee.department,
                punch_in=now,
                punch_out=None,
                duration_seconds=None,
                status="PUNCHED_IN",
                punch_in_confidence=match["confidence"],
                updated_at=now,
            )
            self._apply_security_fields(record, security_fields)
            record.save()
            self._sync_admin_attendance(employee, "PUNCH_IN", now, security_fields=security_fields)

            response = {
                "success": True,
                "recognized": True,
                "action": "PUNCH_IN",
                "message": "Punch-in successful.",
                "attendance_id": str(record.id),
                "employee_id": employee.employee_id,
                "employee_name": employee.name,
                "department": employee.department,
                "employee_image_url": f"/api/v1/attendance/employees/{employee.employee_id}/image",
                "confidence": match["confidence"],
                "liveness": liveness,
                "punch_in": now.isoformat(),
                "punch_out": None,
                "duration_seconds": None,
                "duration_human": None,
            }
            if security_fields:
                response.update(security_fields)
            return response

        duration_seconds = int((now - open_record.punch_in).total_seconds())
        open_record.punch_out = now
        open_record.duration_seconds = duration_seconds
        open_record.status = "PUNCHED_OUT"
        open_record.punch_out_confidence = match["confidence"]
        open_record.updated_at = now
        self._apply_security_fields(open_record, security_fields)
        open_record.save()
        self._sync_admin_attendance(
            employee,
            "PUNCH_OUT",
            now,
            punch_in_time=open_record.punch_in,
            security_fields=security_fields,
        )

        response = {
            "success": True,
            "recognized": True,
            "action": "PUNCH_OUT",
            "message": "Punch-out successful.",
            "attendance_id": str(open_record.id),
            "employee_id": employee.employee_id,
            "employee_name": employee.name,
            "department": employee.department,
            "employee_image_url": f"/api/v1/attendance/employees/{employee.employee_id}/image",
            "confidence": match["confidence"],
            "liveness": liveness,
            "punch_in": open_record.punch_in.isoformat(),
            "punch_out": now.isoformat(),
            "duration_seconds": duration_seconds,
            "duration_human": self._format_duration(duration_seconds),
        }
        if security_fields:
            response.update(security_fields)
        return response

    def get_employee_image(self, employee_id: str) -> tuple[bytes, str]:
        employee = EmployeeFace.objects(employee_id=employee_id).only("image", "image_content_type").first()
        if employee is None or not employee.image:
            raise HTTPException(status_code=404, detail="Employee image nahi mili.")
        return bytes(employee.image), employee.image_content_type or "image/jpeg"

    def get_employee_records(self, employee_id: str, limit: int = 20) -> list[dict[str, Any]]:
        records = AttendanceRecord.objects(employee_id=employee_id).order_by("-punch_in").limit(limit)
        return [
            {
                "attendance_id": str(record.id),
                "employee_id": record.employee_id,
                "employee_name": record.employee_name,
                "department": record.department,
                "status": record.status,
                "punch_in": record.punch_in.isoformat() if record.punch_in else None,
                "punch_out": record.punch_out.isoformat() if record.punch_out else None,
                "duration_seconds": record.duration_seconds,
                "duration_human": self._format_duration(record.duration_seconds)
                if record.duration_seconds is not None
                else None,
            }
            for record in records
        ]

    def _format_duration(self, total_seconds: int) -> str:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
