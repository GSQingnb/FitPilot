"""Exercise query repository."""
import uuid
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.exercise import Exercise


class ExerciseRepository:
    """Encapsulates exercise query operations."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, exercise_id: uuid.UUID) -> Optional[Exercise]:
        result = await self._session.execute(
            select(Exercise).where(Exercise.id == exercise_id, Exercise.is_active == True)
        )
        return result.scalar_one_or_none()

    async def list_filtered(
        self,
        primary_muscle: Optional[str] = None,
        equipment: Optional[str] = None,
        difficulty: Optional[str] = None,
        movement_pattern: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Exercise], int]:
        """Return filtered, paginated exercises and total count.

        Only returns is_active=True exercises.
        """
        base = select(Exercise).where(Exercise.is_active == True)

        if primary_muscle:
            base = base.where(Exercise.primary_muscle == primary_muscle)
        if equipment:
            base = base.where(Exercise.equipment == equipment)
        if difficulty:
            base = base.where(Exercise.difficulty == difficulty)
        if movement_pattern:
            base = base.where(Exercise.movement_pattern == movement_pattern)
        if search:
            base = base.where(Exercise.name.ilike(f"%{search}%"))

        # Total count
        count_q = select(func.count()).select_from(base.subquery())
        total = await self._session.scalar(count_q) or 0

        # Paginated results
        q = base.order_by(Exercise.name).offset(offset).limit(min(limit, 100))
        result = await self._session.execute(q)
        exercises = list(result.scalars().all())

        return exercises, total

    async def seed_exercises(self, exercises_data: List[dict]) -> int:
        """Insert exercises if they don't already exist (by name). Returns count added."""
        added = 0
        for data in exercises_data:
            existing = await self._session.execute(
                select(Exercise).where(Exercise.name == data["name"])
            )
            if existing.scalar_one_or_none() is None:
                exercise = Exercise(**data)
                self._session.add(exercise)
                added += 1
        await self._session.flush()
        return added

    async def count(self) -> int:
        count_q = select(func.count()).select_from(
            select(Exercise).where(Exercise.is_active == True).subquery()
        )
        return await self._session.scalar(count_q) or 0
