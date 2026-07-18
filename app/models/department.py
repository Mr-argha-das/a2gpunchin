from mongoengine import StringField

from app.models.base import BaseDocument


class Department(BaseDocument):
    meta = {"collection": "departments", "indexes": ["tenant_id", "company_id", "department_code", {"fields": ["tenant_id", "company_id", "department_code"], "unique": True}]}

    department_name = StringField(required=True)
    department_code = StringField(required=True)
    description = StringField()
