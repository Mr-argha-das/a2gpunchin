import threading
import time as monotonic_time
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status

from app.core.config import settings
from app.core.tenant import current_company_id, current_is_super_admin, current_tenant_id, current_user_id, tenant_context
from app.models.attendance import Attendance
from app.models.branch import Branch
from app.models.employee import Employee
from app.models.user import User
from app.repositories.base import BaseRepository
from app.services.base import BaseService
from app.utils.geo import within_geofence


class AttendanceService(BaseService):
    search_fields = ["attendance_status", "ip_address"]
    select_related_depth = 2
    _maintenance_lock = threading.Lock()
    _last_maintenance_at_by_scope: dict[tuple[str | None, str | None, bool], float] = {}

    def __init__(self):
        super().__init__(BaseRepository(Attendance))

    def queueable_maintenance_context(self) -> dict:
        return tenant_context()

    def run_request_maintenance(self, context: dict | None = None, max_age_seconds: int = 300) -> bool:
        context = context or {}
        scope = (
            context.get("tenant_id"),
            context.get("company_id"),
            bool(context.get("is_super_admin")),
        )
        now = monotonic_time.monotonic()
        with self._maintenance_lock:
            last_run = self._last_maintenance_at_by_scope.get(scope, 0)
            if now - last_run < max_age_seconds:
                return False
            self._last_maintenance_at_by_scope[scope] = now

        tenant_token = current_tenant_id.set(context.get("tenant_id"))
        company_token = current_company_id.set(context.get("company_id"))
        user_token = current_user_id.set(context.get("user_id"))
        super_token = current_is_super_admin.set(bool(context.get("is_super_admin")))
        try:
            self.sync_missing_face_attendance_records(limit=100)
            self.auto_punch_out_overdue()
            self.recalculate_existing_attendance(limit=100)
            return True
        finally:
            current_tenant_id.reset(tenant_token)
            current_company_id.reset(company_token)
            current_user_id.reset(user_token)
            current_is_super_admin.reset(super_token)

    def _employee_for_user(self, user: User) -> Employee:
        employee = Employee.objects.visible().filter(user_id=user).first() or Employee.objects.visible().filter(email=user.email).first()
        if not employee:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee profile is not linked to this login")
        if not employee.branch_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Employee branch is not assigned")
        if not employee.shift_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Employee shift is not assigned")
        return employee

    def _shift_datetime(self, day: date, value: str) -> datetime:
        hour, minute = [int(part) for part in value.split(":")]
        return datetime.combine(day, time(hour=hour, minute=minute), tzinfo=self._local_tz())

    def _local_tz(self):
        return ZoneInfo(getattr(settings, "default_timezone", "Asia/Kolkata"))

    def local_now(self) -> datetime:
        return datetime.now(self._local_tz())

    def utc_now(self) -> datetime:
        return datetime.now(timezone.utc)

    def local_date(self) -> date:
        return self.local_now().date()

    def _aware(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def to_local(self, value: datetime | None) -> datetime | None:
        if not value:
            return None
        return self._aware(value).astimezone(self._local_tz())

    def _shift_window(self, shift, day: date) -> tuple[datetime, datetime]:
        start_at = self._shift_datetime(day, shift.start_time)
        end_at = self._shift_datetime(day, shift.end_time)
        if shift.is_night_shift or end_at <= start_at:
            end_at += timedelta(days=1)
        return start_at, end_at

    def _check_in_status(self, shift, check_in_at: datetime) -> str:
        local_check_in = self.to_local(check_in_at) or check_in_at
        start_at, _ = self._shift_window(shift, local_check_in.date())
        late_minutes = max(0, int((local_check_in - start_at).total_seconds() // 60))
        after_half_day_after = getattr(shift, "after_half_day_after", 0) or 0
        if after_half_day_after and late_minutes > after_half_day_after:
            return "after_half_day"
        if shift.half_day_after and late_minutes > shift.half_day_after:
            return "half_day"
        late_after = getattr(shift, "late_after", 0) or getattr(shift, "grace_time", 0) or 0
        if late_minutes > late_after:
            return "late"
        return "on_time"

    def _check_out_status(self, shift, check_out_at: datetime) -> str:
        local_check_out = self.to_local(check_out_at) or check_out_at
        _, end_at = self._shift_window(shift, local_check_out.date())
        early_minutes = int((end_at - local_check_out).total_seconds() // 60)
        if shift.early_logout_before and early_minutes > shift.early_logout_before:
            return "early_logout"
        return "normal"

    def _auto_punch_out_time(self, attendance: Attendance) -> datetime | None:
        if not attendance.shift_id or not attendance.attendance_date:
            return None
        _, shift_end_at = self._shift_window(attendance.shift_id, attendance.attendance_date)
        return shift_end_at.astimezone(timezone.utc)

    def main_status_label(self, attendance: Attendance) -> str:
        if attendance.attendance_status == "rejected":
            return "Rejected"
        if attendance.attendance_status == "pending":
            return "Pending"

        statuses = []
        check_in_status = attendance.check_in_status
        check_out_status = attendance.check_out_status
        if check_in_status == "after_half_day":
            statuses.append("After Half Day")
        elif check_in_status == "half_day":
            statuses.append("Half Day")
        elif check_in_status == "late":
            statuses.append("Late")

        if check_out_status == "auto_punch_out":
            statuses.append("Auto Punch Out")
        elif check_out_status == "early_logout":
            statuses.append("Early Logout")

        return " + ".join(statuses) if statuses else "Present"

    def recalculate_attendance_status(self, attendance: Attendance, save: bool = True) -> Attendance:
        if attendance.attendance_status == "approved" and attendance.shift_id:
            if attendance.check_in_time:
                attendance.check_in_status = self._check_in_status(attendance.shift_id, attendance.check_in_time)
            if attendance.check_out_time and attendance.check_out_status != "auto_punch_out":
                attendance.check_out_status = self._check_out_status(attendance.shift_id, attendance.check_out_time)
            if attendance.check_in_time and attendance.check_out_time:
                attendance.total_work_minutes = max(
                    0,
                    int(
                        (
                            self._aware(attendance.check_out_time)
                            - self._aware(attendance.check_in_time)
                        ).total_seconds()
                        // 60
                    ),
                )
            if save:
                attendance.save()
        return attendance

    def recalculate_existing_attendance(self, limit: int = 1000) -> int:
        updated = 0
        records = (
            Attendance.objects.visible()
            .filter(attendance_status="approved", shift_id__ne=None, check_in_time__ne=None)
            .order_by("-attendance_date", "-created_at")
            .limit(max(1, min(limit, 2000)))
        )
        for attendance in records:
            before = (
                attendance.check_in_status,
                attendance.check_out_status,
                attendance.total_work_minutes,
            )
            self.recalculate_attendance_status(attendance, save=False)
            after = (
                attendance.check_in_status,
                attendance.check_out_status,
                attendance.total_work_minutes,
            )
            if before != after:
                attendance.save()
                updated += 1
        return updated

    def _sync_face_record_auto_punch_out(self, attendance: Attendance, auto_out_at: datetime) -> None:
        employee = attendance.employee_id
        if not employee:
            return
        try:
            from app.services.attendence_service import AttendanceRecord
        except Exception:
            return

        employee_keys = [value for value in [getattr(employee, "employee_code", None), str(employee.id)] if value]
        record = (
            AttendanceRecord.objects(employee_id__in=employee_keys, status="PUNCHED_IN")
            .order_by("-punch_in")
            .first()
        )
        if not record:
            return

        punch_out_at = auto_out_at.replace(tzinfo=None) if auto_out_at.tzinfo else auto_out_at
        record.punch_out = punch_out_at
        if record.punch_in:
            record.duration_seconds = max(0, int((punch_out_at - record.punch_in).total_seconds()))
        record.status = "PUNCHED_OUT"
        record.updated_at = datetime.utcnow()
        record.save()

    def auto_punch_out_overdue(self, now: datetime | None = None) -> int:
        now_utc = self._aware(now or self.utc_now()).astimezone(timezone.utc)
        grace_minutes = max(0, getattr(settings, "auto_punch_out_after_minutes", 30))
        open_records = Attendance.objects.visible().filter(
            attendance_status="approved",
            check_in_time__ne=None,
            check_out_time=None,
            shift_id__ne=None,
        )
        updated = 0
        for attendance in open_records:
            auto_out_at = self._auto_punch_out_time(attendance)
            if not auto_out_at:
                continue
            due_at = auto_out_at + timedelta(minutes=grace_minutes)
            if now_utc < due_at:
                continue
            attendance.check_out_time = auto_out_at
            attendance.check_out_status = "auto_punch_out"
            if attendance.check_in_time:
                start = self._aware(attendance.check_in_time)
                attendance.total_work_minutes = max(0, int((auto_out_at - start).total_seconds() // 60))
            attendance.save()
            self._sync_face_record_auto_punch_out(attendance, auto_out_at)
            updated += 1
        return updated

    def auto_punch_out_overdue_for_employee(self, employee: Employee, now: datetime | None = None) -> int:
        now_utc = self._aware(now or self.utc_now()).astimezone(timezone.utc)
        grace_minutes = max(0, getattr(settings, "auto_punch_out_after_minutes", 30))
        open_records = Attendance.objects(
            employee_id=employee,
            attendance_status="approved",
            check_in_time__ne=None,
            check_out_time=None,
            shift_id__ne=None,
            is_active=True,
        )
        updated = 0
        for attendance in open_records:
            auto_out_at = self._auto_punch_out_time(attendance)
            if not auto_out_at:
                continue
            due_at = auto_out_at + timedelta(minutes=grace_minutes)
            if now_utc < due_at:
                continue
            attendance.check_out_time = auto_out_at
            attendance.check_out_status = "auto_punch_out"
            if attendance.check_in_time:
                start = self._aware(attendance.check_in_time)
                attendance.total_work_minutes = max(0, int((auto_out_at - start).total_seconds() // 60))
            attendance.save()
            self._sync_face_record_auto_punch_out(attendance, auto_out_at)
            updated += 1
        return updated

    def sync_missing_face_attendance_records(self, limit: int = 500) -> int:
        try:
            from app.services.attendence_service import AttendanceRecord
        except Exception:
            return 0

        synced = 0
        records = AttendanceRecord.objects.order_by("-punch_in").limit(max(1, min(limit, 1000)))
        for record in records:
            employee = Employee.objects(employee_code=record.employee_id, is_active=True).first()
            if not employee:
                try:
                    employee = Employee.objects(id=record.employee_id, is_active=True).first()
                except Exception:
                    employee = None
            if not employee or not employee.branch_id or not record.punch_in:
                continue

            attendance = Attendance.objects(
                employee_id=employee,
                check_in_time=record.punch_in,
                is_active=True,
            ).first()
            if not attendance:
                attendance = Attendance(
                    tenant_id=employee.tenant_id,
                    company_id=employee.company_id,
                    employee_id=employee,
                    branch_id=employee.branch_id,
                    shift_id=employee.shift_id,
                    attendance_date=(self.to_local(record.punch_in) or record.punch_in).date(),
                    check_in_time=record.punch_in,
                    latitude=employee.branch_id.latitude,
                    longitude=employee.branch_id.longitude,
                    distance_from_office=0,
                    device_info="face-attendance-api",
                    attendance_status="approved",
                    check_in_status=self._check_in_status(employee.shift_id, record.punch_in)
                    if employee.shift_id
                    else "pending",
                )
                synced += 1

            if record.punch_out and not attendance.check_out_time:
                attendance.check_out_time = record.punch_out
                synced += 1

            self.recalculate_attendance_status(attendance, save=False)
            attendance.save()
        return synced

    def today_for_employee(self, user: User) -> dict:
        employee = self._employee_for_user(user)
        attendance = Attendance.objects.visible().filter(employee_id=employee, attendance_date=self.local_date()).first()
        return {
            "employee_id": str(employee.id),
            "employee_name": f"{employee.first_name} {employee.last_name}",
            "branch_id": str(employee.branch_id.id),
            "branch_name": employee.branch_id.branch_name,
            "shift_id": str(employee.shift_id.id),
            "shift_name": employee.shift_id.shift_name,
            "shift_start": employee.shift_id.start_time,
            "shift_end": employee.shift_id.end_time,
            "attendance": None if not attendance else {
                "id": str(attendance.id),
                "check_in_time": self.to_local(attendance.check_in_time).isoformat() if attendance.check_in_time else None,
                "check_out_time": self.to_local(attendance.check_out_time).isoformat() if attendance.check_out_time else None,
                "attendance_status": attendance.attendance_status,
                "check_in_status": attendance.check_in_status,
                "check_out_status": attendance.check_out_status,
                "total_work_minutes": attendance.total_work_minutes,
                "distance_from_office": attendance.distance_from_office,
            },
        }

    def check_in(self, data: dict, ip_address: str | None) -> Attendance:
        employee = Employee.objects.visible().filter(id=data["employee_id"]).first()
        branch = Branch.objects.visible().filter(id=data["branch_id"]).first() if data.get("branch_id") else employee.branch_id if employee else None
        if not employee or not branch:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee branch is not assigned")
        open_attendance = (
            Attendance.objects.visible()
            .filter(employee_id=employee, attendance_date=self.local_date(), check_in_time__ne=None, check_out_time=None)
            .first()
        )
        if open_attendance:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Employee is already punched in. Use manual punch-out first.")
        latitude = data.get("latitude", branch.latitude)
        longitude = data.get("longitude", branch.longitude)
        approved, distance = (True, 0) if data.get("latitude") is None or data.get("longitude") is None else within_geofence(latitude, longitude, branch.latitude, branch.longitude, branch.allowed_radius)
        now = self.utc_now()
        attendance = Attendance(
            tenant_id=employee.tenant_id,
            company_id=employee.company_id,
            employee_id=employee,
            branch_id=branch,
            attendance_date=self.to_local(now).date(),
            check_in_time=now,
            shift_id=employee.shift_id,
            latitude=latitude,
            longitude=longitude,
            distance_from_office=distance,
            device_info=data.get("device_info"),
            browser_fingerprint=data.get("browser_fingerprint"),
            ip_address=ip_address,
            attendance_status="approved" if approved else "rejected",
            check_in_status=self._check_in_status(employee.shift_id, now) if approved and employee.shift_id else "pending",
            rejection_reason=None if approved else f"Outside allowed radius of {branch.allowed_radius} meters",
        )
        for field in (
            "face_score",
            "liveness_score",
            "reflection_score",
            "recognition_score",
            "confidence_score",
            "challenge_type",
            "challenge_result",
            "color_sequence",
            "processing_time",
        ):
            if field in data:
                setattr(attendance, field, data.get(field))
        self.recalculate_attendance_status(attendance, save=False)
        attendance.save()
        return attendance

    def punch_in(self, user: User, data: dict, ip_address: str | None) -> Attendance:
        employee = self._employee_for_user(user)
        existing = Attendance.objects.visible().filter(employee_id=employee, attendance_date=self.local_date()).first()
        if existing and existing.check_in_time:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already punched in today")
        payload = {
            "employee_id": str(employee.id),
            "branch_id": str(employee.branch_id.id),
            **data,
        }
        return self.check_in(payload, ip_address)

    def check_out(self, attendance_id: str, data: dict, allow_manual_correction: bool = False) -> Attendance:
        self.auto_punch_out_overdue()
        attendance = self.repository.get(attendance_id)
        if attendance.attendance_status != "approved" and not allow_manual_correction:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rejected attendance cannot be checked out")
        if attendance.check_out_time:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already punched out")
        branch = attendance.branch_id
        latitude = data.get("latitude", branch.latitude)
        longitude = data.get("longitude", branch.longitude)
        approved, distance = (True, 0) if data.get("latitude") is None or data.get("longitude") is None else within_geofence(latitude, longitude, branch.latitude, branch.longitude, branch.allowed_radius)
        if not approved:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Outside allowed radius by {distance} meters")
        attendance.check_out_time = self.utc_now()
        if allow_manual_correction:
            attendance.attendance_status = "approved"
            attendance.rejection_reason = None
        attendance.latitude = latitude
        attendance.longitude = longitude
        attendance.distance_from_office = distance
        if attendance.check_in_time and attendance.check_out_time:
            attendance.total_work_minutes = max(0, int((self._aware(attendance.check_out_time) - self._aware(attendance.check_in_time)).total_seconds() // 60))
        if attendance.shift_id:
            attendance.check_out_status = self._check_out_status(attendance.shift_id, attendance.check_out_time)
        self.recalculate_attendance_status(attendance, save=False)
        attendance.device_info = data.get("device_info") or attendance.device_info
        attendance.browser_fingerprint = data.get("browser_fingerprint") or attendance.browser_fingerprint
        attendance.save()
        return attendance

    def check_out_employee(self, employee_id: str, data: dict) -> Attendance:
        employee = Employee.objects.visible().filter(id=employee_id).first()
        if not employee:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
        attendance = (
            Attendance.objects.visible()
            .filter(employee_id=employee, check_in_time__ne=None, check_out_time=None)
            .order_by("-attendance_date", "-created_at")
            .first()
        )
        if not attendance:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No open punch-in found for this employee")
        return self.check_out(str(attendance.id), data, allow_manual_correction=True)

    def punch_out(self, user: User, data: dict) -> Attendance:
        self.auto_punch_out_overdue()
        employee = self._employee_for_user(user)
        attendance = Attendance.objects.visible().filter(employee_id=employee, attendance_date=self.local_date()).first()
        if not attendance or not attendance.check_in_time:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Punch in is required before punch out")
        if attendance.check_out_time:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already punched out today")
        return self.check_out(str(attendance.id), data)
