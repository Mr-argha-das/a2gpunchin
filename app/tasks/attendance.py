from app.services.attendance import AttendanceService
from app.tasks.celery_app import celery_app


@celery_app.task
def auto_punch_out_overdue_attendance() -> int:
    return AttendanceService().auto_punch_out_overdue()
