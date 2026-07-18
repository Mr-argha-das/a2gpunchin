from mongoengine import BooleanField, ReferenceField, StringField

from app.models.base import BaseDocument
from app.models.user import User


class Notification(BaseDocument):
    meta = {"collection": "notifications", "indexes": ["tenant_id", "company_id", "recipient", "is_read"]}

    recipient = ReferenceField(User)
    channel = StringField(required=True, choices=("email", "browser", "whatsapp"))
    subject = StringField(required=True)
    message = StringField(required=True)
    status = StringField(default="queued", choices=("queued", "sent", "failed"))
    is_read = BooleanField(default=False)
