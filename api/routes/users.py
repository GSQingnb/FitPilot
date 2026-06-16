"""User API routes."""
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_user, verify_user_ownership
from api.dependencies.database import get_db
from api.schemas import UserCreate, UserResponse
from database.models.user import User
from database.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(body: UserCreate, db: AsyncSession = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    """Create a new user. Requires authentication. Returns 409 if email already exists."""
    repo = UserRepository(db)
    if await repo.email_exists(body.email):
        raise HTTPException(status_code=409, detail="Email already registered")
    try:
        user = await repo.create(email=body.email, display_name=body.display_name)
        await db.commit()
        await db.refresh(user)
        return user
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered")
    except Exception as e:
        await db.rollback()
        logger.error(f"Create user failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    """Get a user by ID. Only the owning user can access."""
    verify_user_ownership(current_user, str(user_id))
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user
