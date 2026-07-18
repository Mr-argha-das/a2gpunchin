from datetime import datetime

from mongoengine import DateTimeField, FloatField, IntField, StringField

from app.models.base import BaseDocument


class Subscription(BaseDocument):
    meta = {"collection": "subscriptions", "indexes": ["tenant_id", "company_id", "status", "end_date"]}

    plan_name = StringField(required=True, choices=("basic", "professional", "enterprise"))
    employee_limit = IntField(default=50)
    branch_limit = IntField(default=1)
    amount = FloatField(default=0)
    currency = StringField(default="INR")
    start_date = DateTimeField(required=True)
    end_date = DateTimeField(required=True)
    status = StringField(default="active", choices=("active", "expired", "cancelled"))
    payment_reference = StringField()

    @property
    def is_expired(self) -> bool:
        return self.end_date < datetime.utcnow()
