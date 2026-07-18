from contextvars import ContextVar

current_tenant_id: ContextVar[str | None] = ContextVar("current_tenant_id", default=None)
current_company_id: ContextVar[str | None] = ContextVar("current_company_id", default=None)
current_user_id: ContextVar[str | None] = ContextVar("current_user_id", default=None)
current_is_super_admin: ContextVar[bool] = ContextVar("current_is_super_admin", default=False)


def tenant_context() -> dict[str, str | None]:
    return {
        "tenant_id": current_tenant_id.get(),
        "company_id": current_company_id.get(),
        "user_id": current_user_id.get(),
        "is_super_admin": current_is_super_admin.get(),
    }
