from starlette.middleware.base import BaseHTTPMiddleware

from app.core.tenant import current_company_id, current_tenant_id, current_user_id
from app.models.audit_log import AuditLog


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api") and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            try:
                AuditLog(
                    tenant_id=current_tenant_id.get() or "platform",
                    company_id=current_company_id.get(),
                    user_id=current_user_id.get(),
                    module=request.url.path.split("/")[2] if len(request.url.path.split("/")) > 2 else "api",
                    action=f"{request.method} {request.url.path}",
                    ip_address=request.client.host if request.client else None,
                    metadata={"status_code": response.status_code},
                ).save()
            except Exception:
                pass
        return response
