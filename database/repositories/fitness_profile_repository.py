"""Fitness profile CRUD repository."""
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database.models.fitness_profile import FitnessProfile


class FitnessProfileRepository:
    """Encapsulates common fitness profile database operations."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def upsert(
        self,
        user_id: uuid.UUID,
        goal: str,
        experience_level: str,
        weekly_frequency: int,
        session_duration_minutes: int,
        available_equipment: list,
        target_muscles: list,
        excluded_exercises: list,
        limitations: Optional[str] = None,
    ) -> FitnessProfile:
        """Create or update a fitness profile. Returns the profile (not committed)."""
        existing = await self.get_by_user_id(user_id)
        if existing:
            existing.goal = goal
            existing.experience_level = experience_level
            existing.weekly_frequency = weekly_frequency
            existing.session_duration_minutes = session_duration_minutes
            existing.available_equipment = available_equipment
            existing.target_muscles = target_muscles
            existing.excluded_exercises = excluded_exercises
            existing.limitations = limitations
            await self._session.flush()
            return existing
        else:
            profile = FitnessProfile(
                user_id=user_id,
                goal=goal,
                experience_level=experience_level,
                weekly_frequency=weekly_frequency,
                session_duration_minutes=session_duration_minutes,
                available_equipment=available_equipment,
                target_muscles=target_muscles,
                excluded_exercises=excluded_exercises,
                limitations=limitations,
            )
            self._session.add(profile)
            await self._session.flush()
            return profile

    async def get_by_user_id(self, user_id: uuid.UUID) -> Optional[FitnessProfile]:
        result = await self._session.execute(
            select(FitnessProfile).where(FitnessProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()
