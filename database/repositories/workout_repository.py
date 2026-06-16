"""Workout repository — data access for workout sessions, exercises, and sets."""
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models.workout_session import WorkoutSession, WorkoutStatus
from database.models.workout_exercise import WorkoutExercise, ExerciseStatus
from database.models.workout_set import WorkoutSet
from database.models.training_day import TrainingDay
from database.models.planned_exercise import PlannedExercise


class WorkoutRepository:
    """Data access for workout execution and tracking."""

    def __init__(self, session: AsyncSession):
        self._session = session

    # ── Sessions ────────────────────────────────────────────────────────────

    async def create_session_from_plan(
        self,
        user_id: uuid.UUID,
        training_plan_id: uuid.UUID,
        training_day_id: uuid.UUID,
        planned_exercises: List[PlannedExercise],
    ) -> WorkoutSession:
        """Create a new workout session and copy planned exercises as workout exercises."""
        session = WorkoutSession(
            user_id=user_id,
            training_plan_id=training_plan_id,
            training_day_id=training_day_id,
            status=WorkoutStatus.IN_PROGRESS,
        )
        self._session.add(session)
        await self._session.flush()

        for pe in planned_exercises:
            we = WorkoutExercise(
                workout_session_id=session.id,
                planned_exercise_id=pe.id,
                exercise_id=pe.exercise_id,
                order_index=pe.order_index,
                status=ExerciseStatus.PENDING,
            )
            self._session.add(we)

        await self._session.flush()
        return session

    async def get_current_for_user(self, user_id: uuid.UUID) -> Optional[WorkoutSession]:
        result = await self._session.execute(
            select(WorkoutSession)
            .where(
                WorkoutSession.user_id == user_id,
                WorkoutSession.status == WorkoutStatus.IN_PROGRESS,
            )
            .options(
                selectinload(WorkoutSession.training_day),
                selectinload(WorkoutSession.workout_exercises)
                .selectinload(WorkoutExercise.workout_sets),
                selectinload(WorkoutSession.workout_exercises)
                .selectinload(WorkoutExercise.exercise),
                selectinload(WorkoutSession.workout_exercises)
                .selectinload(WorkoutExercise.planned_exercise),
            )
        )
        return result.scalar_one_or_none()

    async def get_session_detail(self, session_id: uuid.UUID) -> Optional[WorkoutSession]:
        result = await self._session.execute(
            select(WorkoutSession)
            .where(WorkoutSession.id == session_id)
            .options(
                selectinload(WorkoutSession.training_day),
                selectinload(WorkoutSession.workout_exercises)
                .selectinload(WorkoutExercise.workout_sets),
                selectinload(WorkoutSession.workout_exercises)
                .selectinload(WorkoutExercise.exercise),
                selectinload(WorkoutSession.workout_exercises)
                .selectinload(WorkoutExercise.planned_exercise),
            )
        )
        return result.scalar_one_or_none()

    async def get_session_for_user(self, session_id: uuid.UUID, user_id: uuid.UUID) -> Optional[WorkoutSession]:
        result = await self._session.execute(
            select(WorkoutSession)
            .where(WorkoutSession.id == session_id, WorkoutSession.user_id == user_id)
            .options(
                selectinload(WorkoutSession.training_day),
                selectinload(WorkoutSession.workout_exercises)
                .selectinload(WorkoutExercise.workout_sets),
                selectinload(WorkoutSession.workout_exercises)
                .selectinload(WorkoutExercise.exercise),
                selectinload(WorkoutSession.workout_exercises)
                .selectinload(WorkoutExercise.planned_exercise),
            )
        )
        return result.scalar_one_or_none()

    async def list_sessions(
        self,
        user_id: uuid.UUID,
        status: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        training_plan_id: Optional[uuid.UUID] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[WorkoutSession], int]:
        base = select(WorkoutSession).where(WorkoutSession.user_id == user_id)
        if status:
            base = base.where(WorkoutSession.status == status)
        if date_from:
            base = base.where(WorkoutSession.started_at >= date_from)
        if date_to:
            base = base.where(WorkoutSession.started_at <= date_to)
        if training_plan_id:
            base = base.where(WorkoutSession.training_plan_id == training_plan_id)

        count_q = select(func.count()).select_from(base.subquery())
        total = await self._session.scalar(count_q) or 0

        q = base.order_by(WorkoutSession.started_at.desc()).offset(offset).limit(limit)
        q = q.options(
            selectinload(WorkoutSession.workout_exercises).selectinload(WorkoutExercise.workout_sets),
            selectinload(WorkoutSession.training_day),
        )
        result = await self._session.execute(q)
        sessions = list(result.scalars().all())
        return sessions, total

    async def update_session_status(self, session_id: uuid.UUID, status: WorkoutStatus,
                                     completed_at: Optional[datetime] = None,
                                     duration_seconds: Optional[int] = None,
                                     notes: Optional[str] = None,
                                     perceived_difficulty: Optional[float] = None) -> None:
        """Update session status using ORM (not raw SQL) to handle enum conversion correctly."""
        session = await self._session.get(WorkoutSession, session_id)
        if session is None:
            return
        session.status = status
        if completed_at:
            session.completed_at = completed_at
        if duration_seconds is not None:
            session.duration_seconds = duration_seconds
        if notes is not None:
            session.notes = notes
        if perceived_difficulty is not None:
            session.perceived_difficulty = perceived_difficulty
        await self._session.flush()

    # ── Exercises ────────────────────────────────────────────────────────────

    async def get_exercise(self, exercise_id: uuid.UUID) -> Optional[WorkoutExercise]:
        result = await self._session.execute(
            select(WorkoutExercise)
            .where(WorkoutExercise.id == exercise_id)
            .options(selectinload(WorkoutExercise.workout_sets))
        )
        return result.scalar_one_or_none()

    async def update_exercise_status(self, exercise_id: uuid.UUID, status: ExerciseStatus,
                                      notes: Optional[str] = None) -> None:
        """Update exercise status using ORM for correct enum handling."""
        ex = await self._session.get(WorkoutExercise, exercise_id)
        if ex is None:
            return
        ex.status = status
        if notes is not None:
            ex.notes = notes
        await self._session.flush()

    async def count_completed_sets(self, workout_exercise_id: uuid.UUID) -> int:
        q = select(func.count()).where(
            WorkoutSet.workout_exercise_id == workout_exercise_id,
            WorkoutSet.is_completed == True,
        )
        return await self._session.scalar(q) or 0

    # ── Sets ─────────────────────────────────────────────────────────────────

    async def add_set(self, workout_exercise_id: uuid.UUID, data: dict) -> WorkoutSet:
        ws = WorkoutSet(workout_exercise_id=workout_exercise_id, **data)
        self._session.add(ws)
        await self._session.flush()
        return ws

    async def get_set(self, set_id: uuid.UUID) -> Optional[WorkoutSet]:
        result = await self._session.execute(
            select(WorkoutSet).where(WorkoutSet.id == set_id)
        )
        return result.scalar_one_or_none()

    async def get_set_for_session(self, set_id: uuid.UUID, session_id: uuid.UUID) -> Optional[WorkoutSet]:
        result = await self._session.execute(
            select(WorkoutSet)
            .join(WorkoutExercise, WorkoutSet.workout_exercise_id == WorkoutExercise.id)
            .where(
                WorkoutSet.id == set_id,
                WorkoutExercise.workout_session_id == session_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_set(self, set_id: uuid.UUID, data: dict) -> None:
        await self._session.execute(
            update(WorkoutSet).where(WorkoutSet.id == set_id).values(**data)
        )
        await self._session.flush()

    async def delete_set(self, set_id: uuid.UUID) -> None:
        ws = await self.get_set(set_id)
        if ws:
            await self._session.delete(ws)
            await self._session.flush()

    async def get_set_count_for_session(self, session_id: uuid.UUID) -> int:
        q = select(func.count()).select_from(WorkoutSet).join(
            WorkoutExercise, WorkoutSet.workout_exercise_id == WorkoutExercise.id
        ).where(
            WorkoutExercise.workout_session_id == session_id,
            WorkoutSet.is_completed == True,
        )
        return await self._session.scalar(q) or 0
