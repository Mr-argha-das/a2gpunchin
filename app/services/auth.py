from fastapi import HTTPException, status
from pymongo.errors import ConfigurationError, OperationFailure, PyMongoError, ServerSelectionTimeoutError

from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.models.user import User


class AuthService:
    def login(self, email: str, password: str) -> dict[str, str]:
        try:
            user = User.objects(email=email.lower(), is_active=True).first()
        except OperationFailure as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MongoDB authentication failed. Check Atlas database username, password, auth database, and user permissions.",
            ) from exc
        except (ConfigurationError, ServerSelectionTimeoutError, PyMongoError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MongoDB connection failed. Check MONGODB_URI and Atlas network access.",
            ) from exc
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        claims = {
            "tenant_id": user.tenant_id,
            "company_id": user.company_id,
            "is_super_admin": user.is_super_admin,
            "access_level": getattr(user, "access_level", "employee"),
        }
        return {
            "access_token": create_access_token(str(user.id), claims),
            "refresh_token": create_refresh_token(str(user.id), claims),
            "token_type": "bearer",
        }

    def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
        user.password_hash = hash_password(new_password)
        user.save()

    def request_password_reset(self, email: str) -> None:
        # Queue email in a production integration. Keep response neutral to prevent account enumeration.
        User.objects(email=email.lower(), is_active=True).first()
