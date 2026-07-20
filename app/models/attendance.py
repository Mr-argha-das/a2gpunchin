<<<<<<< HEAD
from mongoengine import (
    BooleanField,
    DateField,
    DateTimeField,
    DictField,
    FloatField,
    IntField,
    ListField,
    ReferenceField,
    StringField,
)
=======
from mongoengine import DateField, DateTimeField, DictField, FloatField, IntField, ListField, ReferenceField, StringField
>>>>>>> 9e6f34479ca642074c023b58f5f761ba7338cbf6

from app.models.base import BaseDocument
from app.models.branch import Branch
from app.models.employee import Employee
from app.models.shift import Shift


class Attendance(BaseDocument):
    meta = {
        "collection": "attendance",
        "indexes": [
            "tenant_id",
            "company_id",
            "employee_id",
            "attendance_date",
            "attendance_status",
            ("tenant_id", "company_id", "attendance_date"),
            ("tenant_id", "company_id", "attendance_date", "attendance_status"),
            ("tenant_id", "company_id", "attendance_date", "check_in_status"),
            ("tenant_id", "company_id", "attendance_date", "branch_id"),
            ("tenant_id", "company_id", "employee_id", "attendance_date"),
        ],
    }

    employee_id = ReferenceField(Employee, required=True)
    branch_id = ReferenceField(Branch, required=True)
    shift_id = ReferenceField(Shift)
    attendance_date = DateField(required=True)
    check_in_time = DateTimeField()
    check_out_time = DateTimeField()
    latitude = FloatField(required=True)
    longitude = FloatField(required=True)
    distance_from_office = FloatField(required=True)
    device_info = StringField()
    browser_fingerprint = StringField()
    ip_address = StringField()
    attendance_status = StringField(default="pending", choices=("approved", "rejected", "pending"))
    check_in_status = StringField(default="pending", choices=("pending", "on_time", "late", "half_day", "after_half_day"))
    check_out_status = StringField(default="pending", choices=("pending", "normal", "early_logout", "auto_punch_out"))
    total_work_minutes = IntField(default=0)
    rejection_reason = StringField()
    selfie_path = StringField()
    
    challenge_type = StringField()
    challenge_result = BooleanField(default=False)

    color_sequence = ListField(StringField())

    face_score = FloatField(default=0.0)
    liveness_score = FloatField(default=0.0)
    reflection_score = FloatField(default=0.0)
    recognition_score = FloatField(default=0.0)
    confidence_score = FloatField(default=0.0)

    processing_time = FloatField(default=0.0)

    security_audit = DictField(default=dict)
