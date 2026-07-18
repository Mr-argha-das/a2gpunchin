from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_token
from app.core.tenant import current_company_id, current_is_super_admin, current_tenant_id, current_user_id
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> User:
    token = credentials.credentials if credentials else request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = User.objects(id=payload["sub"], is_active=True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    current_user_id.set(str(user.id))
    current_tenant_id.set(user.tenant_id)
    current_company_id.set(user.company_id)
    current_is_super_admin.set(user.is_super_admin)
    return user


def require_permissions(*permissions: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.is_super_admin:
            return user
        from app.services.access_control import access_level_for_user

        if access_level_for_user(user) == "admin":
            return user
        granted = {permission.code for role in user.roles for permission in role.permissions}
        missing = [permission for permission in permissions if permission not in granted]
        if missing:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing permissions: {', '.join(missing)}")
        return user

    return checker


def request_tenant(request: Request) -> str | None:
    return getattr(request.state, "tenant_id", None)
