"""FastAPI dependencies for authentication."""
import os
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.database import get_db
from database.models.user import User
from services.auth_service import AuthService, AuthError

bearer_scheme = HTTPBearer(auto_error=False)


async def get_optional_auth_service(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[AuthService]:
    """Returns AuthService if token is present, None otherwise. Does not enforce."""
    if credentials is None:
        return None
    return AuthService(db)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Require valid access token. Returns authenticated User or raises 401."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    svc = AuthService(db)
    try:
        return await svc.get_current_user_from_token(credentials.credentials)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def verify_user_ownership(current_user: User, target_user_id: str) -> None:
    """Raise 403 if current_user does not own target_user_id."""
    if str(current_user.id) != str(target_user_id):
        raise HTTPException(status_code=403, detail="Access denied")
