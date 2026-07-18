from mongoengine import EmailField, StringField

from app.models.base import BaseDocument


class Tenant(BaseDocument):
    meta = {"collection": "tenants", "indexes": ["tenant_id", "domain", "is_active"]}

    name = StringField(required=True, max_length=150)
    domain = StringField(required=True, unique=True)
    owner_email = EmailField(required=True)
    status = StringField(default="active", choices=("active", "suspended"))
