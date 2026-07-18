from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status

from app.models.branch import Branch
from app.models.asset import Asset
from app.models.company import Company
from app.models.department import Department
from app.models.employee import Employee
from app.models.rbac import Permission, Role
from app.models.shift import Shift
from app.models.subscription import Subscription
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.base import BaseRepository
from app.core.security import hash_password
from app.services.access_control import scoped_employees_for_user, sync_employee_user
from app.services.base import BaseService


COMPANY_ADMIN_PERMISSIONS = [
    "assets:create", "assets:read", "assets:update", "assets:delete",
    "branches:create", "branches:read", "branches:update", "branches:delete",
    "departments:create", "departments:read", "departments:update", "departments:delete",
    "employees:create", "employees:read", "employees:update", "employees:delete",
    "shifts:create", "shifts:read", "shifts:update", "shifts:delete",
    "attendance:create", "attendance:read", "attendance:update", "attendance:delete",
    "leaves:create", "leaves:read", "leaves:update", "leaves:delete", "leaves:approve",
    "reports:read",
]


class CompanyService(BaseService):
    search_fields = ["company_name", "company_code", "email"]

    def __init__(self):
        super().__init__(BaseRepository(Company))

    def create(self, data: dict):
        admin_first_name = data.pop("admin_first_name", "Company")
        admin_last_name = data.pop("admin_last_name", "Admin")
        admin_email = data.pop("admin_email", None) or data["email"]
        admin_phone = data.pop("admin_phone", None)
        admin_password = data.pop("admin_password", "CompanyAdmin123!")

        tenant = Tenant(
            tenant_id=data["company_code"].lower(),
            name=data["company_name"],
            domain=f"{data['company_code'].lower()}.local",
            owner_email=admin_email,
        ).save()
        company = Company(tenant_id=str(tenant.id), **data).save()
        company.company_id = str(company.id)
        company.save()

        permissions = []
        for code in COMPANY_ADMIN_PERMISSIONS:
            permission = Permission.objects(code=code).first() or Permission(
                tenant_id=str(tenant.id),
                company_id=str(company.id),
                code=code,
                name=code.replace(":", " ").title(),
                module=code.split(":")[0],
            ).save()
            permissions.append(permission)

        role = Role(
            tenant_id=str(tenant.id),
            company_id=str(company.id),
            name="Company Admin",
            slug=f"company-admin-{data['company_code'].lower()}",
            permissions=permissions,
        ).save()
        User(
            tenant_id=str(tenant.id),
            company_id=str(company.id),
            email=admin_email.lower(),
            password_hash=hash_password(admin_password),
            first_name=admin_first_name,
            last_name=admin_last_name,
            phone=admin_phone,
            roles=[role],
            is_email_verified=True,
        ).save()
        return company


class BranchService(BaseService):
    search_fields = ["branch_name", "branch_code", "address"]

    def __init__(self):
        super().__init__(BaseRepository(Branch))


class DepartmentService(BaseService):
    search_fields = ["department_name", "department_code", "description"]

    def __init__(self):
        super().__init__(BaseRepository(Department))


class AssetService(BaseService):
    search_fields = ["asset_id", "asset_name", "asset_type", "brand_model", "serial_number", "sim_number", "condition", "note"]
    reference_fields = {"employee_id"}
    select_related_depth = 2

    def __init__(self):
        super().__init__(BaseRepository(Asset))

    def _normalize_reference_ids(self, data: dict) -> dict:
        for field in self.reference_fields:
            if field not in data:
                continue
            value = data[field]
            if value in (None, "", "-"):
                data.pop(field)
                continue
            if isinstance(value, str):
                try:
                    data[field] = ObjectId(value)
                except InvalidId as exc:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid {field.replace('_', ' ')} selected.") from exc
        return data

    def create(self, data: dict):
        return super().create(self._normalize_reference_ids(data))

    def update(self, object_id: str, data: dict):
        return super().update(object_id, self._normalize_reference_ids(data))

    def list(self, page: int = 1, page_size: int = 20, search: str | None = None, sort: str = "-created_at", **filters):
        return super().list(page=page, page_size=page_size, search=search, sort=sort, **self._normalize_reference_ids(filters))


class EmployeeService(BaseService):
    search_fields = ["employee_code", "first_name", "last_name", "email", "phone"]
    reference_fields = {"department_id", "branch_id", "shift_id", "reporting_manager"}
    select_related_depth = 2

    def __init__(self):
        super().__init__(BaseRepository(Employee))

    def _as_bool(self, value) -> bool:
        if isinstance(value, bool):
            return value
        return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

    def _normalize_reference_ids(self, data: dict) -> dict:
        for field in self.reference_fields:
            if field not in data:
                continue
            value = data[field]
            if value in (None, "", "-"):
                data.pop(field)
                continue
            if isinstance(value, str):
                try:
                    data[field] = ObjectId(value)
                except InvalidId as exc:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid {field.replace('_', ' ')} selected.") from exc
        return data

    def list(self, page: int = 1, page_size: int = 20, search: str | None = None, sort: str = "-created_at", **filters):
        current_user = filters.pop("current_user", None)
        if current_user:
            scoped_employees = scoped_employees_for_user(current_user)
            if scoped_employees is not None:
                filters["id__in"] = [employee.id for employee in scoped_employees]
        items, total = super().list(page=page, page_size=page_size, search=search, sort=sort, **filters)
        if not search or total or " " not in search.strip():
            return items, total

        query = Employee.objects.visible()
        if filters:
            query = query.filter(**{key: value for key, value in filters.items() if value not in (None, "")})
        for part in search.split():
            query = query.filter(__raw__={"$or": [{"first_name": {"$regex": part, "$options": "i"}}, {"last_name": {"$regex": part, "$options": "i"}}]})
        total = query.count()
        return list(query.order_by(sort).skip((page - 1) * page_size).limit(page_size)), total

    def create(self, data: dict):
        data = self._normalize_reference_ids(data)
        portal_access = self._as_bool(data.pop("portal_access", False))
        access_level = data.pop("access_level", None)
        module_access = data.pop("module_access", None)
        login_password = data.pop("login_password", None)
        data["portal_access"] = portal_access
        data["access_level"] = access_level or data.get("staff_role") or "employee"
        if module_access is not None:
            data["module_access"] = module_access
        if data.get("face_embedding"):
            data["face_enrolled"] = True
        employee = super().create(data)
        if portal_access:
            sync_employee_user(employee, True, access_level or employee.staff_role or "employee", login_password, module_access)
        return employee

    def update(self, object_id: str, data: dict):
        data = self._normalize_reference_ids(data)
        portal_access = data.pop("portal_access", None)
        access_level = data.pop("access_level", None)
        module_access = data.pop("module_access", None)
        login_password = data.pop("login_password", None)
        if portal_access is not None:
            data["portal_access"] = self._as_bool(portal_access)
        if access_level is not None:
            data["access_level"] = access_level
        if module_access is not None:
            data["module_access"] = module_access
        if data.get("face_embedding"):
            data["face_enrolled"] = True
        employee = super().update(object_id, data)
        if data.get("status") and employee.user_id and not employee.user_id.is_super_admin:
            employee.user_id.status = "active" if employee.status == "active" else "inactive"
            employee.user_id.is_active = employee.status == "active"
            employee.user_id.save()
        if portal_access is not None and not self._as_bool(portal_access) and employee.user_id and not employee.user_id.is_super_admin:
            employee.user_id.status = "inactive"
            employee.user_id.is_active = False
            employee.user_id.save()
        if self._as_bool(portal_access):
            sync_employee_user(employee, True, access_level or employee.staff_role or "employee", login_password, module_access)
        return employee


class ShiftService(BaseService):
    search_fields = ["shift_name", "start_time", "end_time"]

    def __init__(self):
        super().__init__(BaseRepository(Shift))


class SubscriptionService(BaseService):
    search_fields = ["plan_name", "payment_reference"]

    def __init__(self):
        super().__init__(BaseRepository(Subscription))
