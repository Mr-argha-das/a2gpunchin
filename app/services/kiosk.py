from fastapi import HTTPException, status

from app.core.config import settings
from app.models.attendance import Attendance
from app.models.branch import Branch
from app.models.employee import Employee
from app.services.attendance import AttendanceService
from app.utils.face import best_face_match
from app.utils.geo import within_geofence


class KioskService:
    def __init__(self):
        self.attendance_service = AttendanceService()

    def login(self, branch_code: str, kiosk_pin: str) -> Branch:
        branch = Branch.objects(branch_code=branch_code, kiosk_pin=kiosk_pin, is_active=True).first()
        if not branch:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid branch code or kiosk PIN")
        return branch

    def _branch(self, branch_id: str, kiosk_pin: str) -> Branch:
        branch = Branch.objects(id=branch_id, kiosk_pin=kiosk_pin, is_active=True).first()
        if not branch:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid kiosk session")
        return branch

    def _employee_scope(self, branch: Branch) -> dict:
        scope = {"tenant_id": branch.tenant_id, "face_enrolled": True, "is_active": True, "status": "active"}
        if branch.company_id:
            scope["company_id"] = branch.company_id
        return scope

    def _match_employee(self, branch: Branch, face_embedding: list[float]) -> tuple[Employee, float]:
        candidates = Employee.objects(**self._employee_scope(branch))
        employee, score = best_face_match(face_embedding, candidates)
        if not employee:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Face not matched. Best score: {score}")
        if not employee.shift_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Matched employee has no shift assigned")
        return employee, score

    def _last_punch_at(self, attendance: Attendance | None):
        if not attendance:
            return None
        values = [value for value in [attendance.check_in_time, attendance.check_out_time] if value]
        return max(values) if values else None

    def _enforce_scan_cooldown(self, attendance: Attendance | None, now) -> None:
        last_punch_at = self._last_punch_at(attendance)
        if not last_punch_at:
            return
        cooldown_seconds = max(0, getattr(settings, "face_punch_cooldown_seconds", 10))
        elapsed = (self.attendance_service._aware(now) - self.attendance_service._aware(last_punch_at)).total_seconds()
        if elapsed < cooldown_seconds:
            remaining = max(1, int(cooldown_seconds - elapsed))
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=f"Please wait {remaining} seconds before next face punch")

    def punch(self, data: dict) -> dict:
        branch = self._branch(data["branch_id"], data["kiosk_pin"])
        employee, score = self._match_employee(branch, data["face_embedding"])
        now = self.attendance_service.utc_now()
        self.attendance_service.auto_punch_out_overdue(now)
        latitude = data.get("latitude") if data.get("latitude") is not None else branch.latitude
        longitude = data.get("longitude") if data.get("longitude") is not None else branch.longitude
        approved, distance = within_geofence(latitude, longitude, branch.latitude, branch.longitude, branch.allowed_radius)
        if not approved:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Kiosk device is outside branch radius by {distance} meters")

        attendance = Attendance.objects(employee_id=employee, attendance_date=self.attendance_service.to_local(now).date(), is_active=True).first()
        self._enforce_scan_cooldown(attendance, now)
        action = data["action"]
        if action == "auto":
            action = "punch_out" if attendance and attendance.check_in_time and not attendance.check_out_time else "punch_in"

        if action == "punch_in":
            if attendance and attendance.check_in_time:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{employee.first_name} already punched in")
            attendance = Attendance(
                tenant_id=employee.tenant_id,
                company_id=employee.company_id,
                employee_id=employee,
                branch_id=employee.branch_id or branch,
                shift_id=employee.shift_id,
                attendance_date=self.attendance_service.to_local(now).date(),
                check_in_time=now,
                latitude=latitude,
                longitude=longitude,
                distance_from_office=distance,
                device_info=data.get("device_info"),
                browser_fingerprint=data.get("browser_fingerprint"),
                attendance_status="approved",
                check_in_status=self.attendance_service._check_in_status(employee.shift_id, now),
            ).save()
        else:
            if not attendance or not attendance.check_in_time:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{employee.first_name} has not punched in")
            if attendance.check_out_time:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{employee.first_name} already punched out")
            attendance.check_out_time = now
            attendance.latitude = latitude
            attendance.longitude = longitude
            attendance.distance_from_office = distance
            attendance.total_work_minutes = max(0, int((self.attendance_service._aware(attendance.check_out_time) - self.attendance_service._aware(attendance.check_in_time)).total_seconds() // 60))
            attendance.check_out_status = self.attendance_service._check_out_status(employee.shift_id, now)
            attendance.device_info = data.get("device_info") or attendance.device_info
            attendance.browser_fingerprint = data.get("browser_fingerprint") or attendance.browser_fingerprint
            attendance.save()

        return {
            "employee_id": str(employee.id),
            "employee_code": employee.employee_code,
            "employee_name": f"{employee.first_name} {employee.last_name}",
            "match_score": score,
            "action": action,
            "attendance_id": str(attendance.id),
            "check_in_status": attendance.check_in_status,
            "check_out_status": attendance.check_out_status,
            "total_work_minutes": attendance.total_work_minutes,
        }

    def enroll_face(self, data: dict) -> dict:
        branch = self._branch(data["branch_id"], data["kiosk_pin"])
        employee = Employee.objects(
            tenant_id=branch.tenant_id,
            company_id=branch.company_id,
            employee_code=data["employee_code"],
            is_active=True,
        ).first()
        if not employee:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found in this company")
        employee.face_embedding = data["face_embedding"]
        employee.face_enrolled = True
        employee.save()
        return {
            "employee_id": str(employee.id),
            "employee_code": employee.employee_code,
            "employee_name": f"{employee.first_name} {employee.last_name}",
            "face_enrolled": employee.face_enrolled,
            "embedding_size": len(employee.face_embedding or []),
        }
