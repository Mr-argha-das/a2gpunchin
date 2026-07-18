from starlette.middleware.base import BaseHTTPMiddleware

from app.core.security import decode_token
from app.core.tenant import current_company_id, current_is_super_admin, current_tenant_id


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        tenant_id = request.headers.get("X-Tenant-ID")
        company_id = request.headers.get("X-Company-ID")
        is_super_admin = False
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                payload = decode_token(auth_header.removeprefix("Bearer ").strip())
                tenant_id = payload.get("tenant_id") or tenant_id
                company_id = payload.get("company_id") or company_id
                is_super_admin = bool(payload.get("is_super_admin"))
            except ValueError:
                pass
        request.state.tenant_id = tenant_id
        request.state.company_id = company_id
        tenant_token = current_tenant_id.set(tenant_id)
        company_token = current_company_id.set(company_id)
        super_token = current_is_super_admin.set(is_super_admin)
        try:
            response = await call_next(request)
        finally:
            current_tenant_id.reset(tenant_token)
            current_company_id.reset(company_token)
            current_is_super_admin.reset(super_token)
        return response
