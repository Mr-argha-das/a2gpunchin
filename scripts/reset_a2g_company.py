import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mongoengine.connection import get_db

from app.core.database import connect_database
from app.core.security import hash_password
from app.models import Company, Permission, Role, Subscription, Tenant, User


PASSWORD = "A2G%ASHU%8001"
SUPER_ADMIN_EMAIL = "admin@a2groups.com"
COMPANY_ADMIN_EMAIL = "company-admin@a2groups.org"

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


def drop_all_collections() -> list[str]:
    db = get_db()
    dropped = []
    for collection_name in db.list_collection_names():
        if collection_name.startswith("system."):
            continue
        db.drop_collection(collection_name)
        dropped.append(collection_name)
    return dropped


def reset_face_index() -> None:
    index_dir = Path("data/face_index")
    for file_name in ("employee_faces.faiss", "employee_id_map.pkl"):
        path = index_dir / file_name
        if path.exists():
            path.unlink()


def create_permission(code: str, tenant_id: str, company_id: str) -> Permission:
    return Permission(
        tenant_id=tenant_id,
        company_id=company_id,
        code=code,
        name=code.replace(":", " ").title(),
        module=code.split(":")[0],
    ).save()


def main() -> None:
    connect_database()
    dropped = drop_all_collections()
    reset_face_index()

    tenant = Tenant(
        tenant_id="a2g",
        name="A2G Groups",
        domain="a2groups.org",
        owner_email=SUPER_ADMIN_EMAIL,
        status="active",
    ).save()

    company = Company(
        tenant_id=str(tenant.id),
        company_name="A2G Groups",
        company_code="A2G",
        email=COMPANY_ADMIN_EMAIL,
        phone="",
        address="",
        website="https://hrms.a2groups.org",
        timezone="Asia/Kolkata",
        subscription_plan="enterprise",
        status="active",
    ).save()
    company.company_id = str(company.id)
    company.save()

    permissions = [create_permission(code, str(tenant.id), str(company.id)) for code in PERMISSIONS]

    super_admin_role = Role(
        tenant_id=str(tenant.id),
        company_id=str(company.id),
        name="Super Admin",
        slug="super-admin-a2g",
        permissions=permissions,
    ).save()
    company_admin_permissions = [
        permission
        for permission in permissions
        if not permission.code.startswith(("companies:delete", "subscriptions:delete"))
    ]
    company_admin_role = Role(
        tenant_id=str(tenant.id),
        company_id=str(company.id),
        name="Company Admin",
        slug="company-admin-a2g",
        permissions=company_admin_permissions,
    ).save()

    User(
        tenant_id=str(tenant.id),
        company_id=str(company.id),
        email=SUPER_ADMIN_EMAIL,
        password_hash=hash_password(PASSWORD),
        first_name="A2G",
        last_name="Admin",
        roles=[super_admin_role],
        access_level="admin",
        is_super_admin=True,
        is_email_verified=True,
        status="active",
    ).save()

    User(
        tenant_id=str(tenant.id),
        company_id=str(company.id),
        email=COMPANY_ADMIN_EMAIL,
        password_hash=hash_password(PASSWORD),
        first_name="Company",
        last_name="Admin",
        roles=[company_admin_role],
        access_level="admin",
        is_super_admin=False,
        is_email_verified=True,
        status="active",
    ).save()

    Subscription(
        tenant_id=str(tenant.id),
        company_id=str(company.id),
        plan_name="enterprise",
        employee_limit=10000,
        branch_limit=1000,
        amount=0,
        start_date=datetime.now(timezone.utc),
        end_date=datetime.now(timezone.utc) + timedelta(days=3650),
        status="active",
    ).save()

    print(f"Dropped collections: {', '.join(dropped) if dropped else 'none'}")
    print("Created company: A2G Groups (A2G)")
    print(f"Created super admin: {SUPER_ADMIN_EMAIL}")
    print(f"Created company admin: {COMPANY_ADMIN_EMAIL}")


if __name__ == "__main__":
    main()
