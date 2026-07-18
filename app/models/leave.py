from mongoengine import DateField, IntField, ReferenceField, StringField

from app.models.base import BaseDocument
from app.models.employee import Employee


class Leave(BaseDocument):
    meta = {"collection": "leaves", "indexes": ["tenant_id", "company_id", "employee_id", "status", "start_date"]}

    employee_id = ReferenceField(Employee, required=True)
    leave_type = StringField(required=True, choices=("casual", "sick", "earned", "work_from_home", "half_day"))
    start_date = DateField(required=True)
    end_date = DateField(required=True)
    total_days = IntField(required=True)
    reason = StringField()
    status = StringField(default="pending_manager", choices=("pending_manager", "pending_hr", "approved", "rejected"))
    manager_remarks = StringField()
    hr_remarks = StringField()
