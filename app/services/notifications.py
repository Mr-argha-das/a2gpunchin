from app.models.notification import Notification


class NotificationService:
    def queue(self, recipient, channel: str, subject: str, message: str) -> Notification:
        notification = Notification(recipient=recipient, channel=channel, subject=subject, message=message)
        notification.save()
        return notification
