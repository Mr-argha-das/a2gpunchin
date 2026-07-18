from pydantic import BaseModel, EmailStr


class CompanyCreate(BaseModel):
    company_name: str
    company_code: str
    email: EmailStr
    phone: str | None = None
    address: str | None = None
    website: str | None = None
    logo: str | None = None
    timezone: str = "Asia/Kolkata"
    subscription_plan: str = "basic"
    status: str = "active"
    admin_first_name: str = "Company"
    admin_last_name: str = "Admin"
    admin_email: EmailStr | None = None
    admin_phone: str | None = None
    admin_password: str = "CompanyAdmin123!"


class CompanyUpdate(BaseModel):
    company_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    website: str | None = None
    logo: str | None = None
    timezone: str | None = None
    subscription_plan: str | None = None
    status: str | None = None
