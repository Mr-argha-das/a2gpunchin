from mongoengine import BooleanField, IntField, StringField

from app.models.base import BaseDocument


class Shift(BaseDocument):
    meta = {"collection": "shifts", "indexes": ["tenant_id", "company_id", "shift_name"]}

    shift_name = StringField(required=True)
    start_time = StringField(required=True)
    end_time = StringField(required=True)
    grace_time = IntField(default=0)
    late_after = IntField(default=0)
    half_day_after = IntField(default=0)
    after_half_day_after = IntField(default=0)
    early_logout_before = IntField(default=0)
    is_night_shift = BooleanField(default=False)
