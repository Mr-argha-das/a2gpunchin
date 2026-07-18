from mongoengine import DateField, StringField

from app.models.base import BaseDocument


class Holiday(BaseDocument):
    meta = {"collection": "holidays", "indexes": ["tenant_id", "company_id", "holiday_date"]}

    holiday_name = StringField(required=True)
    holiday_date = DateField(required=True)
    description = StringField()
