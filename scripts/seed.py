import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import connect_database
from app.core.security import hash_password
from app.models import Branch, Company, Department, Employee, Permission, Role, Shift, Subscription, Tenant, User


PERMISSIONS = [
    "companies:create", "companies:read", "companies:update", "companies:delete",
    "branches:create", "branches:read", "branches:update", "branches:delete",
    "departments:create", "departments:read", "departments:update", "departments:delete",
    "employees:create", "employees:read", "employees:update", "employees:delete",
    "shifts:create", "shifts:read", "shifts:update", "shifts:delete",
    "attendance:create", "attendance:read", "attendance:update", "attendance:delete",
    "leaves:create", "leaves:read", "leaves:update", "leaves:delete", "leaves:approve",
    "subscriptions:create", "subscriptions:read", "subscriptions:update", "subscriptions:delete",
    "reports:read",
]

DEMO_FACE_EMBEDDING = [1.0] + [0.0] * 127


def main():
    connect_database()
    tenant = Tenant.objects(domain="platform.local").first() or Tenant(
        tenant_id="platform",
        name="Platform",
        domain="platform.local",
        owner_email="superadmin@example.com",
    ).save()
    company = Company.objects(company_code="DEMO").first() or Company(
        tenant_id=str(tenant.id),
        company_id="demo",
        company_name="Demo Company",
        company_code="DEMO",
        email="admin@demo.local",
        phone="+910000000000",
        address="Demo Office",
        timezone="Asia/Kolkata",
        subscription_plan="professional",
    ).save()
    company.company_id = str(company.id)
    company.save()
    permissions = []
    for code in PERMISSIONS:
        permission = Permission.objects(code=code).first() or Permission(
            tenant_id=str(tenant.id),
            company_id=str(company.id),
            code=code,
            name=code.replace(":", " ").title(),
            module=code.split(":")[0],
        ).save()
        permissions.append(permission)
    role = Role.objects(slug="super-admin").first() or Role(
        tenant_id=str(tenant.id),
        company_id=str(company.id),
        name="Super Admin",
        slug="super-admin",
        permissions=permissions,
    ).save()
    role.permissions = permissions
    role.save()
    User.objects(email="superadmin@example.com").first() or User(
        tenant_id=str(tenant.id),
        company_id=str(company.id),
        email="superadmin@example.com",
        password_hash=hash_password("SuperAdmin123!"),
        first_name="Super",
        last_name="Admin",
        roles=[role],
        is_super_admin=True,
        is_email_verified=True,
    ).save()
    company_permissions = [permission for permission in permissions if not permission.code.startswith(("companies:", "subscriptions:"))]
    company_admin_role = Role.objects(slug="company-admin-demo").first() or Role(
        tenant_id=str(tenant.id),
        company_id=str(company.id),
        name="Company Admin",
        slug="company-admin-demo",
        permissions=company_permissions,
    ).save()
    company_admin_role.permissions = company_permissions
    company_admin_role.save()
    User.objects(email="companyadmin@example.com").first() or User(
        tenant_id=str(tenant.id),
        company_id=str(company.id),
        email="companyadmin@example.com",
        password_hash=hash_password("CompanyAdmin123!"),
        first_name="Company",
        last_name="Admin",
        roles=[company_admin_role],
        is_email_verified=True,
    ).save()
    branch = Branch.objects(branch_code="HQ").first() or Branch(
        tenant_id=str(tenant.id),
        company_id=str(company.id),
        branch_name="Head Office",
        branch_code="HQ",
        address="Demo HQ",
        latitude=19.0760,
        longitude=72.8777,
        allowed_radius=100,
        kiosk_pin="1234",
    ).save()
    branch.kiosk_pin = "1234"
    branch.save()
    department = Department.objects(department_code="HR").first() or Department(
        tenant_id=str(tenant.id),
        company_id=str(company.id),
        department_name="Human Resources",
        department_code="HR",
    ).save()
    shift = Shift.objects(shift_name="General Shift").first() or Shift(
        tenant_id=str(tenant.id),
        company_id=str(company.id),
        shift_name="General Shift",
        start_time="09:00",
        end_time="18:00",
        grace_time=10,
        late_after=15,
        half_day_after=240,
        early_logout_before=30,
    ).save()
    employee_role = Role.objects(slug="employee-demo").first() or Role(
        tenant_id=str(tenant.id),
        company_id=str(company.id),
        name="Employee",
        slug="employee-demo",
        permissions=[permission for permission in permissions if permission.code.startswith("attendance:")],
    ).save()
    employee_role.permissions = [permission for permission in permissions if permission.code.startswith("attendance:")]
    employee_role.save()
    employee_user = User.objects(email="employee@example.com").first() or User(
        tenant_id=str(tenant.id),
        company_id=str(company.id),
        email="employee@example.com",
        password_hash=hash_password("Employee123!"),
        first_name="Rahul",
        last_name="Sharma",
        roles=[employee_role],
        is_email_verified=True,
    ).save()
    employee = Employee.objects(employee_code="EMP001").first() or Employee(
        tenant_id=str(tenant.id),
        company_id=str(company.id),
        employee_code="EMP001",
        first_name="Rahul",
        last_name="Sharma",
        email="employee@example.com",
        phone="+919999999999",
        designation="Employee",
        department_id=department,
        branch_id=branch,
        shift_id=shift,
        user_id=employee_user,
        face_embedding=DEMO_FACE_EMBEDDING,
        face_enrolled=True,
    ).save()
    employee.branch_id = branch
    employee.shift_id = shift
    employee.user_id = employee_user
    employee.face_embedding = DEMO_FACE_EMBEDDING
    employee.face_enrolled = True
    employee.save()
    Subscription.objects(company_id=str(company.id), plan_name="professional").first() or Subscription(
        tenant_id=str(tenant.id),
        company_id=str(company.id),
        plan_name="professional",
        employee_limit=500,
        branch_limit=10,
        amount=9999,
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=365),
        status="active",
    ).save()
    print("Seed complete: superadmin@example.com / SuperAdmin123!, companyadmin@example.com / CompanyAdmin123!, employee@example.com / Employee123!")


if __name__ == "__main__":
    main()
