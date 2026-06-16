"""Authentication API routes — register, login, refresh, logout, me."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import bearer_scheme, get_current_user
from api.dependencies.database import get_db
from api.schemas import RegisterRequest, LoginRequest, AuthTokenResponse
from database.models.user import User
from services.auth_service import AuthService, AuthError
from services.token_store import TokenStoreError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_cookie(response: Response, cookie_dict: dict):
    response.set_cookie(**cookie_dict)


@router.post("/register", response_model=AuthTokenResponse, status_code=201)
async def register(body: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """Register a new user. Returns access token + sets refresh cookie."""
    svc = AuthService(db)
    try:
        data, refresh = await svc.register(body.email, body.display_name, body.password)
        _set_cookie(response, AuthService.make_refresh_cookie(refresh))
        return data
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/login", response_model=AuthTokenResponse)
async def login(body: LoginRequest, request: Request, response: Response,
                db: AsyncSession = Depends(get_db)):
    """Login. Returns access token + sets refresh cookie."""
    client_ip = request.client.host if request.client else "unknown"
    svc = AuthService(db)
    try:
        data, refresh = await svc.login(body.email, body.password, client_ip)
        _set_cookie(response, AuthService.make_refresh_cookie(refresh))
        return data
    except (AuthError, TokenStoreError) as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/me", response_model=dict)
async def me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user profile."""
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "display_name": current_user.display_name,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
    }


@router.post("/refresh", response_model=AuthTokenResponse)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Refresh tokens using HttpOnly cookie."""
    cookie_name = "fitpilot_refresh_token"
    refresh_token = request.cookies.get(cookie_name)
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token not provided")

    svc = AuthService(db)
    try:
        data, new_refresh = await svc.refresh(refresh_token)
        _set_cookie(response, AuthService.make_refresh_cookie(new_refresh))
        return data
    except AuthError as e:
        # Clear invalid cookie
        _set_cookie(response, AuthService.make_clear_cookie())
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except TokenStoreError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Logout — revoke refresh token and clear cookie."""
    cookie_name = "fitpilot_refresh_token"
    refresh_token = request.cookies.get(cookie_name)
    if refresh_token:
        svc = AuthService(db)
        try:
            await svc.logout(refresh_token)
        except Exception:
            pass  # Idempotent — always clear cookie
    _set_cookie(response, AuthService.make_clear_cookie())
