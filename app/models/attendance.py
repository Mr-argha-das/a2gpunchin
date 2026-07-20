from mongoengine import DateField, DateTimeField, DictField, FloatField, IntField, ListField, ReferenceField, StringField

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
    face_score = FloatField()
    liveness_score = FloatField()
    reflection_score = FloatField()
    recognition_score = FloatField()
    confidence_score = FloatField()
    challenge_type = StringField()
    challenge_result = StringField()
    color_sequence = ListField(StringField())
    processing_time = FloatField()
    security_audit = DictField()
