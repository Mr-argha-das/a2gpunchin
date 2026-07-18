from fastapi import APIRouter, Depends, Response

from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, PasswordChangeRequest, PasswordResetRequest, TokenPair
from app.services.auth import AuthService

router = APIRouter()
service = AuthService()


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, response: Response):
    tokens = service.login(payload.email, payload.password)
    response.set_cookie(
        key="access_token",
        value=tokens["access_token"],
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 8,
    )
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    return tokens


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")


@router.post("/password-reset", status_code=202)
def password_reset(payload: PasswordResetRequest):
    service.request_password_reset(payload.email)
    return {"message": "If the account exists, reset instructions will be sent"}


@router.post("/change-password", status_code=204)
def change_password(payload: PasswordChangeRequest, user: User = Depends(get_current_user)):
    service.change_password(user, payload.current_password, payload.new_password)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": str(user.id), "email": user.email, "name": user.full_name, "tenant_id": user.tenant_id, "company_id": user.company_id, "access_level": getattr(user, "access_level", "employee")}
