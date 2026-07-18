from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request

from app.core.dependencies import get_current_user, require_permissions
from app.models.user import User
from app.schemas.attendance import AttendanceCheckIn, AttendanceCheckOut, AttendanceManualCheckOut, PunchLocation
from app.services.access_control import scoped_employees_for_user
from app.services.attendance import AttendanceService
from app.utils.serializers import document_to_dict

router = APIRouter()
service = AttendanceService()


def _status_label(value: str | None) -> str:
    if not value:
        return "-"
    return value.replace("_", " ").title()


def _time_label(value) -> str:
    local_value = service.to_local(value)
    if not local_value:
        return "-"
    return local_value.strftime("%I:%M %p")


def _duration_label(minutes: int) -> str:
    minutes = max(0, minutes)
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours}h {mins}m"
    if hours:
        return f"{hours}h"
    return f"{mins}m"


def _work_minutes(item) -> int:
    if not item.check_in_time:
        return 0
    start = service._aware(item.check_in_time)
    end = service._aware(item.check_out_time) if item.check_out_time else service.utc_now()
    return max(0, int((end - start).total_seconds() // 60))


def _attendance_row(item) -> dict:
    employee = item.employee_id
    branch = item.branch_id
    employee_name = "-"
    if employee:
        employee_name = f"{employee.employee_code} - {employee.first_name} {employee.last_name}".strip()
    branch_name = "-"
    if branch:
        branch_name = f"{branch.branch_name} ({branch.branch_code})"
    local_check_in = service.to_local(item.check_in_time)
    display_date = local_check_in.date() if local_check_in else item.attendance_date
    in_status = item.check_in_status
    out_status = item.check_out_status
    if item.attendance_status == "approved" and item.shift_id:
        if item.check_in_time:
            in_status = service._check_in_status(item.shift_id, item.check_in_time)
        if item.check_out_time and item.check_out_status != "auto_punch_out":
            out_status = service._check_out_status(item.shift_id, item.check_out_time)
    item.check_in_status = in_status
    item.check_out_status = out_status
    return {
        "id": str(item.id),
        "employee": employee_name,
        "branch": branch_name,
        "date": display_date.strftime("%d %b %Y") if display_date else "-",
        "check_in_time": _time_label(item.check_in_time),
        "check_out_time": _time_label(item.check_out_time),
        "status": _status_label(item.attendance_status),
        "main_status": service.main_status_label(item),
        "in_status": _status_label(in_status),
        "out_status": _status_label(out_status),
        "work_minutes": _duration_label(_work_minutes(item)),
    }


@router.get("")
def list_attendance(
    background_tasks: BackgroundTasks,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    employee_id: str | None = None,
    branch_id: str | None = None,
    status: str | None = None,
    user: User = Depends(require_permissions("attendance:read")),
):
    background_tasks.add_task(
        service.run_request_maintenance,
        service.queueable_maintenance_context(),
    )
    filters = {}
    if start_date:
        filters["attendance_date__gte"] = start_date
    if end_date:
        filters["attendance_date__lte"] = end_date
    if employee_id:
        filters["employee_id"] = employee_id
    scoped_employees = scoped_employees_for_user(user)
    if scoped_employees is not None:
        scoped_ids = {str(employee.id) for employee in scoped_employees}
        if employee_id and employee_id not in scoped_ids:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
        filters["employee_id__in"] = scoped_employees
    if branch_id:
        filters["branch_id"] = branch_id
    if status:
        filters["attendance_status"] = status
    items, total = service.list(page=page, page_size=page_size, search=search, **filters)
    return {"items": [_attendance_row(item) for item in items], "total": total, "page": page, "page_size": page_size}


@router.post("/check-in")
def check_in(payload: AttendanceCheckIn, request: Request, _=Depends(require_permissions("attendance:create"))):
    return document_to_dict(service.check_in(payload.model_dump(exclude_none=True), request.client.host if request.client else None))


@router.post("/check-out")
def check_out(payload: AttendanceCheckOut, _=Depends(require_permissions("attendance:update"))):
    data = payload.model_dump(exclude_none=True)
    attendance_id = data.pop("attendance_id")
    return document_to_dict(service.check_out(attendance_id, data))


@router.post("/manual-check-out")
def manual_check_out(payload: AttendanceManualCheckOut, _=Depends(require_permissions("attendance:update"))):
    data = payload.model_dump(exclude_none=True)
    employee_id = data.pop("employee_id")
    return document_to_dict(service.check_out_employee(employee_id, data))


@router.get("/me/today")
def my_attendance_today(user: User = Depends(get_current_user)):
    return service.today_for_employee(user)


@router.post("/punch-in")
def punch_in(payload: PunchLocation, request: Request, user: User = Depends(get_current_user)):
    return document_to_dict(service.punch_in(user, payload.model_dump(exclude_none=True), request.client.host if request.client else None))


@router.post("/punch-out")
def punch_out(payload: PunchLocation, user: User = Depends(get_current_user)):
    return document_to_dict(service.punch_out(user, payload.model_dump(exclude_none=True)))
