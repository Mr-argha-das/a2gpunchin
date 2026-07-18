from datetime import date

from pydantic import BaseModel, EmailStr


class EmployeeCreate(BaseModel):
    employee_code: str
    prefix: str | None = None
    staff_role: str | None = None
    first_name: str
    last_name: str
    father_name: str | None = None
    mother_name: str | None = None
    email: EmailStr
    office_email: EmailStr | None = None
    phone: str | None = None
    emergency_contact_number: str | None = None
    gender: str | None = None
    marital_status: str | None = None
    date_of_birth: date | None = None
    joining_date: date | None = None
    designation: str | None = None
    department_id: str | None = None
    branch_id: str | None = None
    shift_id: str | None = None
    reporting_manager: str | None = None
    profile_photo: str | None = None
    current_address: str | None = None
    permanent_address: str | None = None
    qualification: str | None = None
    work_experience: str | None = None
    note: str | None = None
    aadhar_number: str | None = None
    pan_number: str | None = None
    bank_name: str | None = None
    account_number: str | None = None
    ifsc_code: str | None = None
    face_embedding: list[float] | None = None
    portal_access: bool = False
    access_level: str | None = None
    module_access: list[str] | None = None
    login_password: str | None = None


class EmployeeUpdate(BaseModel):
    prefix: str | None = None
    staff_role: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    father_name: str | None = None
    mother_name: str | None = None
    email: EmailStr | None = None
    office_email: EmailStr | None = None
    phone: str | None = None
    emergency_contact_number: str | None = None
    gender: str | None = None
    marital_status: str | None = None
    date_of_birth: date | None = None
    joining_date: date | None = None
    designation: str | None = None
    department_id: str | None = None
    branch_id: str | None = None
    shift_id: str | None = None
    reporting_manager: str | None = None
    profile_photo: str | None = None
    current_address: str | None = None
    permanent_address: str | None = None
    qualification: str | None = None
    work_experience: str | None = None
    note: str | None = None
    aadhar_number: str | None = None
    pan_number: str | None = None
    bank_name: str | None = None
    account_number: str | None = None
    ifsc_code: str | None = None
    face_embedding: list[float] | None = None
    status: str | None = None
    portal_access: bool | None = None
    access_level: str | None = None
    module_access: list[str] | None = None
    login_password: str | None = None


class EmployeeFaceEnroll(BaseModel):
    face_embedding: list[float]
