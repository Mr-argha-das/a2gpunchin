from datetime import date

from mongoengine import DateField, ReferenceField, StringField

from app.models.base import BaseDocument
from app.models.employee import Employee


class Asset(BaseDocument):
    meta = {
        "collection": "assets",
        "indexes": [
            "tenant_id",
            "company_id",
            "employee_id",
            "asset_type",
            "status",
            "asset_id",
            {"fields": ["tenant_id", "company_id", "asset_id"], "unique": True},
        ],
    }

    employee_id = ReferenceField(Employee, required=True)
    asset_id = StringField(required=True)
    asset_type = StringField(required=True, choices=("pc", "laptop", "keyboard", "mouse", "headset", "sim", "other"))
    asset_name = StringField(required=True)
    brand_model = StringField()
    serial_number = StringField()
    sim_number = StringField()
    assigned_on = DateField(default=date.today)
    returned_on = DateField()
    status = StringField(default="assigned", choices=("assigned", "returned", "repair", "damaged", "lost"))
    condition = StringField()
    note = StringField()
