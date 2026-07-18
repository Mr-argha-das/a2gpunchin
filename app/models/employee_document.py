from mongoengine import DateTimeField, ReferenceField, StringField

from app.models.base import BaseDocument
from app.models.employee import Employee


class EmployeeDocument(BaseDocument):
    meta = {
        "collection": "employee_documents",
        "indexes": [
            "tenant_id",
            "company_id",
            "employee_id",
            "created_at",
            ("tenant_id", "company_id", "employee_id", "-created_at"),
        ],
    }

    employee_id = ReferenceField(Employee, required=True)
    document_name = StringField(required=True)
    original_filename = StringField(required=True)
    stored_filename = StringField(required=True)
    file_path = StringField(required=True)
    content_type = StringField()
    uploaded_at = DateTimeField()
