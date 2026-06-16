"""Training plan repository with transaction-safe operations."""
import uuid
from typing import List, Optional, Tuple

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models.exercise import Exercise
from database.models.training_plan import TrainingPlan, PlanStatus, PlanSource
from database.models.training_day import TrainingDay
from database.models.planned_exercise import PlannedExercise


class TrainingPlanRepository:
    """Transaction-safe CRUD for training plans with full tree support."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_plan_tree(
        self,
        user_id: uuid.UUID,
        name: str,
        goal: str,
        duration_weeks: int,
        weekly_frequency: int,
        overview: Optional[str],
        days_data: List[dict],
    ) -> TrainingPlan:
        """
        Create a full training plan tree in a single transaction.
        Caller is responsible for commit/rollback.
        """
        version = await self.get_next_version(user_id)

        plan = TrainingPlan(
            user_id=user_id,
            name=name,
            goal=goal,
            duration_weeks=duration_weeks,
            weekly_frequency=weekly_frequency,
            status=PlanStatus.DRAFT,
            version=version,
            source=PlanSource.AI_GENERATED,
        )
        self._session.add(plan)
        await self._session.flush()  # get plan.id

        for day_data in days_data:
            day = TrainingDay(
                training_plan_id=plan.id,
                day_index=day_data["day_index"],
                title=day_data["title"],
                notes=day_data.get("notes"),
            )
            self._session.add(day)
            await self._session.flush()

            for ex_data in day_data.get("exercises", []):
                pe = PlannedExercise(
                    training_day_id=day.id,
                    exercise_id=uuid.UUID(ex_data["exercise_id"]),
                    order_index=ex_data["order_index"],
                    sets=ex_data["sets"],
                    reps_min=ex_data["reps_min"],
                    reps_max=ex_data["reps_max"],
                    rest_seconds=ex_data.get("rest_seconds", 90),
                    target_rpe=ex_data.get("target_rpe"),
                    notes=ex_data.get("notes"),
                )
                self._session.add(pe)

        await self._session.flush()
        return plan

    async def get_next_version(self, user_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(TrainingPlan.version), 0))
            .where(TrainingPlan.user_id == user_id)
        )
        return (result.scalar() or 0) + 1

    async def get_by_id(self, plan_id: uuid.UUID) -> Optional[TrainingPlan]:
        result = await self._session.execute(
            select(TrainingPlan)
            .where(TrainingPlan.id == plan_id)
            .options(
                selectinload(TrainingPlan.training_days)
                .selectinload(TrainingDay.planned_exercises)
                .selectinload(PlannedExercise.exercise)
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_for_user(self, plan_id: uuid.UUID, user_id: uuid.UUID) -> Optional[TrainingPlan]:
        result = await self._session.execute(
            select(TrainingPlan)
            .where(TrainingPlan.id == plan_id, TrainingPlan.user_id == user_id)
            .options(
                selectinload(TrainingPlan.training_days)
                .selectinload(TrainingDay.planned_exercises)
                .selectinload(PlannedExercise.exercise)
            )
        )
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: uuid.UUID,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[TrainingPlan], int]:
        base = select(TrainingPlan).where(TrainingPlan.user_id == user_id)
        if status:
            base = base.where(TrainingPlan.status == status)

        count_q = select(func.count()).select_from(base.subquery())
        total = await self._session.scalar(count_q) or 0

        q = base.order_by(TrainingPlan.created_at.desc()).offset(offset).limit(limit)
        result = await self._session.execute(q)
        plans = list(result.scalars().all())
        return plans, total

    async def activate_for_user(self, plan_id: uuid.UUID, user_id: uuid.UUID) -> Optional[TrainingPlan]:
        """Activate a plan: archive all other active plans, activate target. Transaction-safe."""
        # Deactivate all active plans for user
        await self._session.execute(
            update(TrainingPlan)
            .where(TrainingPlan.user_id == user_id, TrainingPlan.status == PlanStatus.ACTIVE)
            .values(status=PlanStatus.ARCHIVED)
        )
        # Activate target
        await self._session.execute(
            update(TrainingPlan)
            .where(TrainingPlan.id == plan_id, TrainingPlan.user_id == user_id)
            .values(status=PlanStatus.ACTIVE)
        )
        await self._session.flush()
        return await self.get_by_id(plan_id)

    async def archive_for_user(self, plan_id: uuid.UUID, user_id: uuid.UUID) -> Optional[TrainingPlan]:
        await self._session.execute(
            update(TrainingPlan)
            .where(TrainingPlan.id == plan_id, TrainingPlan.user_id == user_id)
            .values(status=PlanStatus.ARCHIVED)
        )
        await self._session.flush()
        return await self.get_by_id(plan_id)
