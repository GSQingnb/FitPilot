"""Fitness profile API routes."""
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.database import get_db
from api.schemas import FitnessProfileUpsert, FitnessProfileResponse
from database.repositories.user_repository import UserRepository
from database.repositories.fitness_profile_repository import FitnessProfileRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["fitness-profiles"])


@router.put("/users/{user_id}/fitness-profile", response_model=FitnessProfileResponse)
async def upsert_fitness_profile(
    user_id: uuid.UUID,
    body: FitnessProfileUpsert,
    db: AsyncSession = Depends(get_db),
):
    """Create or update a user's fitness profile. Returns 404 if user not found."""
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    profile_repo = FitnessProfileRepository(db)
    try:
        profile = await profile_repo.upsert(
            user_id=user_id,
            goal=body.goal,
            experience_level=body.experience_level,
            weekly_frequency=body.weekly_frequency,
            session_duration_minutes=body.session_duration_minutes,
            available_equipment=body.available_equipment,
            target_muscles=body.target_muscles,
            excluded_exercises=body.excluded_exercises,
            limitations=body.limitations,
        )
        await db.commit()
        await db.refresh(profile)
        return profile
    except Exception as e:
        await db.rollback()
        logger.error(f"Upsert fitness profile failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/users/{user_id}/fitness-profile", response_model=FitnessProfileResponse)
async def get_fitness_profile(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a user's fitness profile. Returns 404 if not found."""
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    profile_repo = FitnessProfileRepository(db)
    profile = await profile_repo.get_by_user_id(user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Fitness profile not found")
    return profile
