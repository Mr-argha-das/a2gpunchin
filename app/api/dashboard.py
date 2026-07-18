from datetime import date, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends

from app.core.dependencies import require_permissions
from app.models.attendance import Attendance
from app.models.branch import Branch
from app.models.employee import Employee
from app.models.leave import Leave
from app.models.shift import Shift
from app.models.user import User
from app.services.access_control import scoped_employees_for_user
from app.services.attendance import AttendanceService

router = APIRouter()
attendance_service = AttendanceService()


def _percent(value: int, total: int) -> int:
    if total <= 0:
        return 0
    return round((value / total) * 100)


def _status_label(value: str | None) -> str:
    if not value:
        return "-"
    return value.replace("_", " ").title()


def _employee_label(employee: Employee | None) -> str:
    if not employee:
        return "Unassigned employee"
    return f"{employee.employee_code} - {employee.first_name} {employee.last_name}".strip()


def _branch_label(branch: Branch | None) -> str:
    if not branch:
        return "No branch"
    return f"{branch.branch_name} ({branch.branch_code})"


def _first_aggregate(rows: list[dict]) -> dict:
    return rows[0] if rows else {}


def _date_key(value) -> str:
    if hasattr(value, "date"):
        value = value.date()
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


@router.get("/summary")
def dashboard_summary(background_tasks: BackgroundTasks, user: User = Depends(require_permissions("attendance:read"))):
    background_tasks.add_task(
        attendance_service.run_request_maintenance,
        attendance_service.queueable_maintenance_context(),
    )
    today = date.today()

    employees = Employee.objects.visible().filter(status="active")
    scoped_employees = scoped_employees_for_user(user)
    if scoped_employees is not None:
        employees = employees.filter(id__in=[employee.id for employee in scoped_employees])
    branches = Branch.objects.visible()
    shifts = Shift.objects.visible()
    today_attendance = Attendance.objects.visible().filter(attendance_date=today)
    if scoped_employees is not None:
        today_attendance = today_attendance.filter(employee_id__in=scoped_employees)

    employee_stats = _first_aggregate(list(employees.aggregate(
        {
            "$group": {
                "_id": None,
                "total": {"$sum": 1},
                "enrolled": {"$sum": {"$cond": [{"$eq": ["$face_enrolled", True]}, 1, 0]}},
            }
        }
    )))
    total_employees = employee_stats.get("total", 0)
    enrolled_faces = employee_stats.get("enrolled", 0)
    total_branches = branches.count()
    today_stats = _first_aggregate(list(today_attendance.aggregate(
        {
            "$group": {
                "_id": None,
                "present": {"$sum": {"$cond": [{"$eq": ["$attendance_status", "approved"]}, 1, 0]}},
                "rejected": {"$sum": {"$cond": [{"$eq": ["$attendance_status", "rejected"]}, 1, 0]}},
                "pending": {"$sum": {"$cond": [{"$eq": ["$attendance_status", "pending"]}, 1, 0]}},
                "late": {
                    "$sum": {
                        "$cond": [
                            {"$in": ["$check_in_status", ["late", "half_day", "after_half_day"]]},
                            1,
                            0,
                        ]
                    }
                },
                "missing_checkout": {
                    "$sum": {
                        "$cond": [
                            {"$and": [{"$ne": ["$check_in_time", None]}, {"$eq": ["$check_out_time", None]}]},
                            1,
                            0,
                        ]
                    }
                },
                "active_branch_ids": {"$addToSet": "$branch_id"},
            }
        }
    )))
    present_today = today_stats.get("present", 0)
    rejected_today = today_stats.get("rejected", 0)
    pending_today = today_stats.get("pending", 0)
    late_today = today_stats.get("late", 0)
    missing_checkout = today_stats.get("missing_checkout", 0)
    absent_today = max(total_employees - present_today, 0)
    leave_query = Leave.objects.visible().filter(status__in=["pending_manager", "pending_hr"])
    if scoped_employees is not None:
        leave_query = leave_query.filter(employee_id__in=scoped_employees)
    pending_leave = leave_query.count()

    active_branch_ids = {str(branch_id) for branch_id in today_stats.get("active_branch_ids", []) if branch_id}

    employee_branch_counts = {
        str(row["_id"]): row["count"]
        for row in employees.aggregate({"$group": {"_id": "$branch_id", "count": {"$sum": 1}}})
        if row.get("_id")
    }
    attendance_branch_counts = {
        str(row["_id"]): row["count"]
        for row in today_attendance.filter(attendance_status="approved").aggregate({"$group": {"_id": "$branch_id", "count": {"$sum": 1}}})
        if row.get("_id")
    }

    start_day = today - timedelta(days=6)
    attendance_window = Attendance.objects.visible().filter(attendance_date__gte=start_day, attendance_date__lte=today)
    if scoped_employees is not None:
        attendance_window = attendance_window.filter(employee_id__in=scoped_employees)
    trend_counts = {
        _date_key(row["_id"]): row
        for row in attendance_window.aggregate(
            {
                "$group": {
                    "_id": "$attendance_date",
                    "present": {"$sum": {"$cond": [{"$eq": ["$attendance_status", "approved"]}, 1, 0]}},
                    "late": {
                        "$sum": {
                            "$cond": [
                                {"$in": ["$check_in_status", ["late", "half_day", "after_half_day"]]},
                                1,
                                0,
                            ]
                        }
                    },
                    "rejected": {"$sum": {"$cond": [{"$eq": ["$attendance_status", "rejected"]}, 1, 0]}},
                }
            }
        )
    }
    trend = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        counts = trend_counts.get(day.isoformat(), {})
        trend.append(
            {
                "label": day.strftime("%a"),
                "date": day.isoformat(),
                "present": counts.get("present", 0),
                "late": counts.get("late", 0),
                "rejected": counts.get("rejected", 0),
            }
        )

    branch_rows = []
    for branch in branches.order_by("branch_name")[:8]:
        branch_id = str(branch.id)
        approved = attendance_branch_counts.get(branch_id, 0)
        branch_total = employee_branch_counts.get(branch_id, 0)
        branch_rows.append(
            {
                "name": branch.branch_name,
                "code": branch.branch_code,
                "present": approved,
                "employees": branch_total,
                "coverage": _percent(approved, branch_total),
                "status": "Active" if str(branch.id) in active_branch_ids else "No punches",
            }
        )

    exceptions = []
    exception_query = (
        Attendance.objects.visible()
        .filter(
            attendance_date=today,
            __raw__={
                "$or": [
                    {"attendance_status": {"$in": ["rejected", "pending"]}},
                    {"check_in_status": {"$in": ["late", "half_day", "after_half_day"]}},
                    {"check_out_status": "early_logout"},
                    {"check_out_status": "auto_punch_out"},
                    {"check_in_time": {"$ne": None}, "check_out_time": None},
                ]
            },
        )
        .order_by("-created_at")
    )
    if scoped_employees is not None:
        exception_query = exception_query.filter(employee_id__in=scoped_employees)
    for item in exception_query.limit(6).select_related(max_depth=1):
        exceptions.append(
            {
                "employee": _employee_label(item.employee_id),
                "branch": _branch_label(item.branch_id),
                "status": _status_label(item.attendance_status),
                "issue": _status_label(item.rejection_reason or item.check_out_status or item.check_in_status),
            }
        )

    setup_gaps = []
    for employee in employees.filter(face_enrolled=False).order_by("employee_code")[:4]:
        setup_gaps.append({"label": _employee_label(employee), "meta": "Face enrollment pending", "href": "/employees"})
    for employee in employees.filter(shift_id=None).order_by("employee_code")[:3]:
        setup_gaps.append({"label": _employee_label(employee), "meta": "Shift assignment missing", "href": "/employees"})
    for branch in branches.filter(kiosk_pin__in=[None, ""]).order_by("branch_name")[:3]:
        setup_gaps.append({"label": _branch_label(branch), "meta": "Kiosk PIN missing", "href": "/branches"})

    return {
        "date": today.isoformat(),
        "metrics": {
            "present_today": present_today,
            "absent_today": absent_today,
            "late_today": late_today,
            "missing_checkout": missing_checkout,
            "rejected_today": rejected_today,
            "pending_today": pending_today,
            "total_employees": total_employees,
            "total_branches": total_branches,
            "active_kiosks": len(active_branch_ids),
            "configured_shifts": shifts.count(),
            "pending_leave": pending_leave,
            "face_coverage": _percent(enrolled_faces, total_employees),
        },
        "trend": trend,
        "branch_health": branch_rows,
        "exceptions": exceptions,
        "setup_gaps": setup_gaps[:6],
        "enrollment": {
            "enrolled": enrolled_faces,
            "missing": max(total_employees - enrolled_faces, 0),
            "coverage": _percent(enrolled_faces, total_employees),
        },
    }
