from app.core.config import settings


try:
    from celery import Celery
except ImportError:
    class _LocalTaskApp:
        def __init__(self):
            self.conf = {}

        def task(self, fn):
            fn.name = f"{fn.__module__}.{fn.__name__}"
            return fn

    celery_app = _LocalTaskApp()
else:
    celery_app = Celery(
        "attendance_saas",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=["app.tasks.notifications", "app.tasks.attendance"],
    )
    celery_app.conf.timezone = "UTC"
    celery_app.conf.beat_schedule = {
        "auto-punch-out-overdue-attendance": {
            "task": "app.tasks.attendance.auto_punch_out_overdue_attendance",
            "schedule": 15 * 60,
        }
    }
