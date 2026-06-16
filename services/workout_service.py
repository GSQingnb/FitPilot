"""Workout service — state machine, business rules, and orchestration."""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.workout_session import WorkoutSession, WorkoutStatus
from database.models.workout_exercise import WorkoutExercise, ExerciseStatus
from database.models.workout_set import WorkoutSet, SetType
from database.models.training_plan import PlanStatus
from database.models.training_day import TrainingDay
from database.repositories.user_repository import UserRepository
from database.repositories.training_plan_repository import TrainingPlanRepository
from database.repositories.workout_repository import WorkoutRepository


class WorkoutService:
    """Orchestrates workout execution with state machine enforcement."""

    def __init__(self, db: AsyncSession):
        self._db = db
        self._user_repo = UserRepository(db)
        self._plan_repo = TrainingPlanRepository(db)
        self._workout_repo = WorkoutRepository(db)

    # ── Start workout ────────────────────────────────────────────────────────

    async def start_workout(
        self, user_id: uuid.UUID, training_plan_id: uuid.UUID, training_day_id: uuid.UUID
    ) -> dict:
        """Start a new workout from an active training plan."""
        # Validate user
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            raise WorkoutError("User not found", 404)

        # Validate plan ownership and status
        plan = await self._plan_repo.get_by_id_for_user(training_plan_id, user_id)
        if not plan:
            raise WorkoutError("Training plan not found for this user", 404)
        plan_status = str(plan.status.value) if hasattr(plan.status, "value") else str(plan.status)
        if plan_status != "active":
            raise WorkoutError("Training plan must be active to start a workout", 422)

        # Validate training day belongs to plan
        day = None
        for d in plan.training_days:
            if d.id == training_day_id:
                day = d
                break
        if not day:
            raise WorkoutError("Training day not found in this plan", 404)

        # Check for existing in-progress session
        existing = await self._workout_repo.get_current_for_user(user_id)
        if existing:
            raise WorkoutError(
                "User already has an in-progress workout",
                409,
                extra={"session_id": str(existing.id)},
            )

        # Create session and copy exercises
        planned_exercises = sorted(day.planned_exercises or [], key=lambda pe: pe.order_index)
        session = await self._workout_repo.create_session_from_plan(
            user_id=user_id,
            training_plan_id=training_plan_id,
            training_day_id=training_day_id,
            planned_exercises=planned_exercises,
        )
        await self._db.commit()

        loaded = await self._workout_repo.get_session_detail(session.id)
        return _session_to_detail(loaded)

    # ── Get current workout ──────────────────────────────────────────────────

    async def get_current(self, user_id: uuid.UUID) -> Optional[dict]:
        session = await self._workout_repo.get_current_for_user(user_id)
        if not session:
            return None
        return _session_to_detail(session)

    # ── Exercise status ──────────────────────────────────────────────────────

    async def _get_verified_exercise(self, session_id: uuid.UUID, exercise_id: uuid.UUID) -> WorkoutExercise:
        session = await self._workout_repo.get_session_detail(session_id)
        if not session:
            raise WorkoutError("Workout session not found", 404)
        self._check_in_progress(session)

        we = await self._workout_repo.get_exercise(exercise_id)
        if not we or str(we.workout_session_id) != str(session_id):
            raise WorkoutError("Exercise not found in this session", 404)
        return we

    async def start_exercise(self, session_id: uuid.UUID, exercise_id: uuid.UUID) -> dict:
        we = await self._get_verified_exercise(session_id, exercise_id)
        if we.status != ExerciseStatus.PENDING:
            raise WorkoutError(f"Cannot start exercise: current status is {we.status.value}", 409)
        await self._workout_repo.update_exercise_status(exercise_id, ExerciseStatus.IN_PROGRESS)
        await self._db.commit()
        return _exercise_to_dict(await self._workout_repo.get_exercise(exercise_id))

    async def complete_exercise(self, session_id: uuid.UUID, exercise_id: uuid.UUID) -> dict:
        we = await self._get_verified_exercise(session_id, exercise_id)
        if we.status not in (ExerciseStatus.PENDING, ExerciseStatus.IN_PROGRESS):
            raise WorkoutError(f"Cannot complete exercise: current status is {we.status.value}", 409)
        await self._workout_repo.update_exercise_status(exercise_id, ExerciseStatus.COMPLETED)
        await self._db.commit()
        return _exercise_to_dict(await self._workout_repo.get_exercise(exercise_id))

    async def skip_exercise(self, session_id: uuid.UUID, exercise_id: uuid.UUID,
                             reason: Optional[str] = None) -> dict:
        we = await self._get_verified_exercise(session_id, exercise_id)
        if we.status not in (ExerciseStatus.PENDING, ExerciseStatus.IN_PROGRESS):
            raise WorkoutError(f"Cannot skip exercise: current status is {we.status.value}", 409)
        await self._workout_repo.update_exercise_status(exercise_id, ExerciseStatus.SKIPPED, notes=reason)
        await self._db.commit()
        return _exercise_to_dict(await self._workout_repo.get_exercise(exercise_id))

    # ── Sets CRUD ────────────────────────────────────────────────────────────

    async def add_set(self, session_id: uuid.UUID, exercise_id: uuid.UUID, data: dict) -> dict:
        _ = await self._get_verified_exercise(session_id, exercise_id)

        # Validate at least one data point
        if not data.get("reps") and not data.get("duration_seconds") and not data.get("distance_meters"):
            raise WorkoutError("At least one of reps, duration_seconds, or distance_meters required", 422)

        rpe = data.get("rpe")
        if rpe is not None and (rpe < 1 or rpe > 10):
            raise WorkoutError("RPE must be 1-10", 422)

        try:
            wset = await self._workout_repo.add_set(exercise_id, data)
            await self._db.commit()
            return _set_to_dict(wset)
        except IntegrityError:
            await self._db.rollback()
            raise WorkoutError(f"Duplicate set_index {data.get('set_index')} for this exercise", 409)

    async def update_set(self, session_id: uuid.UUID, set_id: uuid.UUID, data: dict) -> dict:
        session = await self._workout_repo.get_session_detail(session_id)
        if not session:
            raise WorkoutError("Workout session not found", 404)
        self._check_in_progress(session)

        wset = await self._workout_repo.get_set_for_session(set_id, session_id)
        if not wset:
            raise WorkoutError("Set not found in this session", 404)

        await self._workout_repo.update_set(set_id, data)
        await self._db.commit()
        updated = await self._workout_repo.get_set(set_id)
        return _set_to_dict(updated)

    async def delete_set(self, session_id: uuid.UUID, set_id: uuid.UUID) -> None:
        session = await self._workout_repo.get_session_detail(session_id)
        if not session:
            raise WorkoutError("Workout session not found", 404)
        self._check_in_progress(session)

        wset = await self._workout_repo.get_set_for_session(set_id, session_id)
        if not wset:
            raise WorkoutError("Set not found in this session", 404)

        await self._workout_repo.delete_set(set_id)
        await self._db.commit()

    # ── Complete / Cancel ────────────────────────────────────────────────────

    async def complete_session(self, session_id: uuid.UUID, notes: Optional[str] = None,
                                perceived_difficulty: Optional[float] = None) -> dict:
        session = await self._workout_repo.get_session_detail(session_id)
        if not session:
            raise WorkoutError("Workout session not found", 404)
        self._check_in_progress(session)

        # Must have at least one completed set
        total_sets = await self._workout_repo.get_set_count_for_session(session_id)
        if total_sets == 0:
            raise WorkoutError("Cannot complete: no completed sets recorded", 422)

        if perceived_difficulty is not None and (perceived_difficulty < 1 or perceived_difficulty > 10):
            raise WorkoutError("perceived_difficulty must be 1-10", 422)

        now = datetime.now(timezone.utc)
        duration = int((now - session.started_at).total_seconds()) if session.started_at else None

        # Auto-complete any still-pending exercises with completed sets
        for we in (session.workout_exercises or []):
            if we.status in (ExerciseStatus.PENDING, ExerciseStatus.IN_PROGRESS):
                set_count = await self._workout_repo.count_completed_sets(we.id)
                new_status = ExerciseStatus.COMPLETED if set_count > 0 else ExerciseStatus.SKIPPED
                await self._workout_repo.update_exercise_status(we.id, new_status)

        await self._workout_repo.update_session_status(
            session_id, WorkoutStatus.COMPLETED,
            completed_at=now, duration_seconds=duration,
            notes=notes, perceived_difficulty=perceived_difficulty,
        )
        await self._db.commit()

        loaded = await self._workout_repo.get_session_detail(session_id)
        return _session_to_detail(loaded)

    async def cancel_session(self, session_id: uuid.UUID, reason: Optional[str] = None) -> dict:
        session = await self._workout_repo.get_session_detail(session_id)
        if not session:
            raise WorkoutError("Workout session not found", 404)
        self._check_in_progress(session)

        now = datetime.now(timezone.utc)
        duration = int((now - session.started_at).total_seconds()) if session.started_at else None

        await self._workout_repo.update_session_status(
            session_id, WorkoutStatus.CANCELLED,
            completed_at=now, duration_seconds=duration,
            notes=reason or session.notes,
        )
        await self._db.commit()

        loaded = await self._workout_repo.get_session_detail(session_id)
        return _session_to_detail(loaded)

    # ── History ──────────────────────────────────────────────────────────────

    async def list_sessions(self, user_id: uuid.UUID, **filters) -> Tuple[List[dict], int]:
        sessions, total = await self._workout_repo.list_sessions(user_id=user_id, **filters)
        items = [_session_to_summary(s) for s in sessions]
        return items, total

    async def get_session(self, user_id: uuid.UUID, session_id: uuid.UUID) -> dict:
        session = await self._workout_repo.get_session_for_user(session_id, user_id)
        if not session:
            raise WorkoutError("Workout session not found", 404)
        return _session_to_detail(session)

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _check_in_progress(session: WorkoutSession):
        if session.status != WorkoutStatus.IN_PROGRESS:
            raise WorkoutError(f"Session is {session.status.value}, not in_progress", 409)


class WorkoutError(Exception):
    def __init__(self, message: str, status_code: int = 400, extra: dict = None):
        self.message = message
        self.status_code = status_code
        self.extra = extra or {}
        super().__init__(message)


# ── Serialization helpers ────────────────────────────────────────────────────

def _session_to_summary(session: WorkoutSession) -> dict:
    exercises = session.workout_exercises or []
    total_sets = sum(len(we.workout_sets or []) for we in exercises)
    completed_sets = sum(
        sum(1 for ws in (we.workout_sets or []) if ws.is_completed)
        for we in exercises
    )

    day_title = None
    if session.training_day:
        day_title = session.training_day.title

    return {
        "id": str(session.id),
        "user_id": str(session.user_id),
        "status": str(session.status.value) if hasattr(session.status, "value") else str(session.status),
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "duration_seconds": session.duration_seconds,
        "training_plan_id": str(session.training_plan_id) if session.training_plan_id else None,
        "training_day_id": str(session.training_day_id) if session.training_day_id else None,
        "training_day_title": day_title,
        "exercise_count": len(exercises),
        "completed_set_count": completed_sets,
        "notes": session.notes,
        "perceived_difficulty": session.perceived_difficulty,
    }


def _session_to_detail(session: WorkoutSession) -> dict:
    base = _session_to_summary(session)
    base["exercises"] = [_exercise_to_dict(we) for we in (session.workout_exercises or [])]

    # Compute stats
    total_reps = 0
    total_volume = 0.0
    completed_ex = 0
    skipped_ex = 0
    for we in (session.workout_exercises or []):
        st = str(we.status.value) if hasattr(we.status, "value") else str(we.status)
        if st == "completed":
            completed_ex += 1
        elif st == "skipped":
            skipped_ex += 1
        for ws in (we.workout_sets or []):
            if ws.is_completed and ws.reps:
                total_reps += ws.reps
                if ws.weight_kg:
                    total_volume += ws.weight_kg * ws.reps

    base["stats"] = {
        "total_exercises": len(session.workout_exercises or []),
        "completed_exercises": completed_ex,
        "skipped_exercises": skipped_ex,
        "total_sets": sum(len(we.workout_sets or []) for we in (session.workout_exercises or [])),
        "completed_sets": base["completed_set_count"],
        "total_reps": total_reps,
        "total_volume": round(total_volume, 1),
    }
    return base


def _exercise_to_dict(we: WorkoutExercise) -> dict:
    ex = we.exercise
    pe = we.planned_exercise
    return {
        "id": str(we.id),
        "exercise_id": str(we.exercise_id),
        "exercise_name": ex.name if ex else "Unknown",
        "primary_muscle": ex.primary_muscle if ex else "",
        "equipment": str(ex.equipment.value) if ex and ex.equipment else "",
        "status": str(we.status.value) if hasattr(we.status, "value") else str(we.status),
        "order_index": we.order_index,
        "planned_sets": pe.sets if pe else None,
        "planned_reps_min": pe.reps_min if pe else None,
        "planned_reps_max": pe.reps_max if pe else None,
        "notes": we.notes,
        "sets": [_set_to_dict(ws) for ws in (we.workout_sets or [])],
    }


def _set_to_dict(ws: WorkoutSet) -> dict:
    return {
        "id": str(ws.id),
        "set_index": ws.set_index,
        "set_type": str(ws.set_type.value) if hasattr(ws.set_type, "value") else str(ws.set_type),
        "weight_kg": ws.weight_kg,
        "reps": ws.reps,
        "duration_seconds": ws.duration_seconds,
        "distance_meters": ws.distance_meters,
        "rpe": ws.rpe,
        "is_completed": ws.is_completed,
        "notes": ws.notes,
    }
