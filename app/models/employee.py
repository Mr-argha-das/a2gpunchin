from datetime import date

from mongoengine import BooleanField, DateField, EmailField, FloatField, ListField, ReferenceField, StringField

from app.models.base import BaseDocument
from app.models.branch import Branch
from app.models.department import Department
from app.models.shift import Shift
from app.models.user import User


class Employee(BaseDocument):
    meta = {
        "collection": "employees",
        "indexes": [
            "tenant_id",
            "company_id",
            "employee_code",
            "branch_id",
            "department_id",
            ("tenant_id", "company_id", "status"),
            ("tenant_id", "company_id", "status", "face_enrolled"),
            ("tenant_id", "company_id", "status", "branch_id"),
            {"fields": ["tenant_id", "company_id", "employee_code"], "unique": True},
        ],
    }

    employee_code = StringField(required=True)
    prefix = StringField()
    staff_role = StringField()
    first_name = StringField(required=True)
    last_name = StringField(required=True)
    father_name = StringField()
    mother_name = StringField()
    email = EmailField(required=True)
    office_email = EmailField()
    phone = StringField()
    emergency_contact_number = StringField()
    gender = StringField(choices=("male", "female", "other", "prefer_not_to_say"))
    marital_status = StringField(choices=("single", "married", "divorced", "widowed"))
    date_of_birth = DateField()
    joining_date = DateField(default=date.today)
    designation = StringField()
    department_id = ReferenceField(Department)
    branch_id = ReferenceField(Branch)
    shift_id = ReferenceField(Shift)
    reporting_manager = ReferenceField("Employee")
    user_id = ReferenceField(User)
    portal_access = BooleanField(default=False)
    access_level = StringField(default="employee", choices=("admin", "manager", "tl", "employee"))
    module_access = ListField(StringField())
    profile_photo = StringField()
    current_address = StringField()
    permanent_address = StringField()
    qualification = StringField()
    work_experience = StringField()
    note = StringField()
    aadhar_number = StringField()
    pan_number = StringField()
    bank_name = StringField()
    account_number = StringField()
    ifsc_code = StringField()
    face_embedding = ListField(FloatField())
    face_enrolled = BooleanField(default=False)
    documents = ListField(StringField())
    status = StringField(default="active", choices=("active", "inactive", "terminated", "transferred"))
