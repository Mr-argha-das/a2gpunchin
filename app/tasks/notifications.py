from app.tasks.celery_app import celery_app


@celery_app.task
def send_notification(notification_id: str) -> bool:
    # Integrate SMTP, browser push, or WhatsApp provider here.
    return bool(notification_id)
