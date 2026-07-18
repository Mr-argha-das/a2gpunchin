from mongoengine import BooleanField, EmailField, ListField, ReferenceField, StringField

from app.models.base import BaseDocument
from app.models.rbac import Role


class User(BaseDocument):
    meta = {"collection": "users", "indexes": ["tenant_id", "company_id", "email", "is_active"]}

    email = EmailField(required=True, unique=True)
    password_hash = StringField(required=True)
    first_name = StringField(required=True)
    last_name = StringField(required=True)
    phone = StringField()
    roles = ListField(ReferenceField(Role))
    access_level = StringField(default="employee", choices=("admin", "manager", "tl", "employee"))
    module_access = ListField(StringField())
    is_super_admin = BooleanField(default=False)
    is_email_verified = BooleanField(default=False)
    status = StringField(default="active", choices=("active", "inactive", "locked"))

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()
