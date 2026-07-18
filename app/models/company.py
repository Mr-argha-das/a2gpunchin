from mongoengine import EmailField, StringField, URLField

from app.models.base import BaseDocument


class Company(BaseDocument):
    meta = {"collection": "companies", "indexes": ["tenant_id", "company_code", "status", {"fields": ["tenant_id", "company_code"], "unique": True}]}

    company_name = StringField(required=True, max_length=180)
    company_code = StringField(required=True)
    email = EmailField(required=True)
    phone = StringField(max_length=30)
    address = StringField()
    website = URLField()
    logo = StringField()
    timezone = StringField(default="Asia/Kolkata")
    subscription_plan = StringField(default="basic")
    status = StringField(default="active", choices=("active", "suspended", "deleted"))
