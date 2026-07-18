from mongoengine import ReferenceField, StringField

from app.models.base import BaseDocument
from app.models.user import User


class SupportTicket(BaseDocument):
    meta = {"collection": "support_tickets", "indexes": ["tenant_id", "company_id", "status"]}

    requester = ReferenceField(User)
    subject = StringField(required=True)
    description = StringField(required=True)
    status = StringField(default="open", choices=("open", "in_progress", "resolved", "closed"))
    priority = StringField(default="medium", choices=("low", "medium", "high", "urgent"))
