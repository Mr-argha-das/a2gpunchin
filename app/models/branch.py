from mongoengine import FloatField, ReferenceField, StringField

from app.models.base import BaseDocument


class Branch(BaseDocument):
    meta = {"collection": "branches", "indexes": ["tenant_id", "company_id", "branch_code", {"fields": ["tenant_id", "company_id", "branch_code"], "unique": True}]}

    branch_name = StringField(required=True)
    branch_code = StringField(required=True)
    address = StringField(required=True)
    latitude = FloatField(required=True, min_value=-90, max_value=90)
    longitude = FloatField(required=True, min_value=-180, max_value=180)
    allowed_radius = FloatField(default=100, min_value=10)
    kiosk_pin = StringField(default="1234")
    branch_manager = ReferenceField("User")
