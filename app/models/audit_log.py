from mongoengine import DictField, StringField

from app.models.base import BaseDocument


class AuditLog(BaseDocument):
    meta = {"collection": "audit_logs", "indexes": ["tenant_id", "company_id", "user_id", "module", "created_at"]}

    user_id = StringField()
    module = StringField(required=True)
    action = StringField(required=True)
    ip_address = StringField()
    metadata = DictField()
