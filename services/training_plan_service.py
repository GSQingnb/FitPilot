"""Training plan orchestration service.

Coordinates: profile lookup → candidate exercises → LLM generation →
validation → transaction save.
"""
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.exercise import Exercise
from database.models.fitness_profile import FitnessProfile
from database.repositories.exercise_repository import ExerciseRepository
from database.repositories.fitness_profile_repository import FitnessProfileRepository
from database.repositories.training_plan_repository import TrainingPlanRepository
from database.repositories.user_repository import UserRepository
from services.plan_generation_service import PlanGenerationService, GeneratedPlan
from services.plan_validation_service import PlanValidationService, ValidationResult

logger = logging.getLogger(__name__)


class TrainingPlanService:
    """Orchestrates the full training plan generation workflow."""

    def __init__(
        self,
        db: AsyncSession,
        api_key: str,
        base_url: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
    ):
        self._db = db
        self._user_repo = UserRepository(db)
        self._profile_repo = FitnessProfileRepository(db)
        self._exercise_repo = ExerciseRepository(db)
        self._plan_repo = TrainingPlanRepository(db)
        self._validator = PlanValidationService()
        self._generator = PlanGenerationService(api_key=api_key, base_url=base_url, model=model)

    async def generate_plan(
        self,
        user_id: uuid.UUID,
        duration_weeks: int = 4,
        plan_name: Optional[str] = None,
        additional_preferences: Optional[str] = None,
    ) -> dict:
        """
        Complete workflow: profile → candidates → LLM → validate → save.
        Returns a dict representation of the saved plan tree.
        """
        t0 = time.monotonic()

        # 1. Verify user exists
        user = await self._user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id)

        # 2. Verify fitness profile exists
        profile = await self._profile_repo.get_by_user_id(user_id)
        if not profile:
            raise ProfileNotFoundError(user_id)

        # 3. Select candidate exercises
        candidates = await self._select_candidates(profile)
        if not candidates:
            raise NoCandidateExercisesError(user_id, profile)

        candidate_dicts = self._exercises_to_dicts(candidates)
        profile_dict = self._profile_to_dict(profile)

        logger.info(
            f"Generating plan for user={user_id}: candidates={len(candidates)}, "
            f"goal={profile_dict['goal']}, equipment={profile_dict['available_equipment']}"
        )

        # 4. Generate with LLM (with retries built in)
        try:
            generated, retries = await self._generator.generate(
                profile=profile_dict,
                candidate_exercises=candidate_dicts,
                additional_preferences=additional_preferences,
                plan_name=plan_name,
            )
        except Exception as e:
            elapsed = (time.monotonic() - t0) * 1000
            logger.error(f"LLM generation failed for user={user_id}: {e}", extra={"elapsed_ms": elapsed})
            raise PlanGenerationError(f"LLM generation failed: {e}")

        # 5. Validate business rules
        plan_dict = generated.model_dump()
        validation = self._validator.validate_plan(plan_dict, profile, candidates)
        if not validation.is_valid:
            errors_str = "; ".join(f"{e.field}: {e.message}" for e in validation.errors)
            logger.warning(
                f"Validation failed for user={user_id}: {errors_str}. Retrying with feedback."
            )
            # Try once more with validation feedback
            try:
                generated, _ = await self._generator.generate(
                    profile=profile_dict,
                    candidate_exercises=candidate_dicts,
                    additional_preferences=f"上一版校验失败: {errors_str}。请修正。"
                    + (f" 用户要求: {additional_preferences}" if additional_preferences else ""),
                    plan_name=plan_name,
                )
                plan_dict = generated.model_dump()
                validation = self._validator.validate_plan(plan_dict, profile, candidates)
                if not validation.is_valid:
                    errors_str2 = "; ".join(f"{e.field}: {e.message}" for e in validation.errors)
                    raise ValidationFailedError(errors_str2)
            except ValidationFailedError:
                raise
            except Exception as e:
                raise ValidationFailedError(f"Validation retry failed: {e}")

        # 6. Save in transaction
        try:
            plan = await self._plan_repo.create_plan_tree(
                user_id=user_id,
                name=plan_dict["name"],
                goal=plan_dict["goal"],
                duration_weeks=plan_dict["duration_weeks"],
                weekly_frequency=plan_dict["weekly_frequency"],
                overview=plan_dict.get("overview"),
                days_data=plan_dict["days"],
            )
            await self._db.commit()
        except Exception as e:
            await self._db.rollback()
            logger.error(f"Transaction failed for user={user_id}: {e}")
            raise PlanSaveError(f"Failed to save plan: {e}")

        # 7. Load full tree for response
        saved_plan = await self._plan_repo.get_by_id(plan.id)
        elapsed = (time.monotonic() - t0) * 1000
        logger.info(
            f"Plan generated and saved: plan_id={plan.id}, user={user_id}, "
            f"retries={retries}, elapsed_ms={elapsed:.0f}"
        )
        return self._plan_to_response(saved_plan)

    async def _select_candidates(self, profile: FitnessProfile) -> List[Exercise]:
        """Select exercises matching the user's equipment, experience, and exclusions."""
        equipment = profile.available_equipment or []
        if not equipment:
            return []

        # Build filter conditions
        all_exercises, total = await self._exercise_repo.list_filtered(limit=200)
        if total == 0:
            return []

        excluded = set(profile.excluded_exercises or [])
        candidates = []

        for ex in all_exercises:
            if not ex.is_active:
                continue
            if ex.name in excluded or str(ex.id) in excluded:
                continue
            # Filter by equipment
            if ex.equipment and str(ex.equipment.value) in equipment:
                candidates.append(ex)

        # Also include bodyweight exercises for any equipment profile
        for ex in all_exercises:
            if ex.equipment and str(ex.equipment.value) == "bodyweight":
                if ex not in candidates and ex.is_active and ex.name not in excluded:
                    candidates.append(ex)

        # Deduplicate
        seen = set()
        final = []
        for c in candidates:
            if c.id not in seen:
                seen.add(c.id)
                final.append(c)

        return final

    def _exercises_to_dicts(self, exercises: List[Exercise]) -> List[dict]:
        return [
            {
                "id": str(e.id),
                "name": e.name,
                "primary_muscle": e.primary_muscle,
                "secondary_muscles": e.secondary_muscles or [],
                "equipment": str(e.equipment.value) if e.equipment else "",
                "difficulty": str(e.difficulty.value) if e.difficulty else "",
                "movement_pattern": e.movement_pattern,
            }
            for e in exercises
        ]

    def _profile_to_dict(self, profile: FitnessProfile) -> dict:
        return {
            "goal": str(profile.goal.value) if hasattr(profile.goal, "value") else str(profile.goal),
            "experience_level": str(profile.experience_level.value) if hasattr(profile.experience_level, "value") else str(profile.experience_level),
            "weekly_frequency": profile.weekly_frequency,
            "session_duration_minutes": profile.session_duration_minutes,
            "available_equipment": profile.available_equipment or [],
            "target_muscles": profile.target_muscles or [],
            "excluded_exercises": profile.excluded_exercises or [],
            "limitations": profile.limitations,
        }

    def _plan_to_response(self, plan) -> dict:
        """Convert ORM object tree to response dict, avoiding lazy loading issues."""
        return {
            "id": str(plan.id),
            "user_id": str(plan.user_id),
            "name": plan.name,
            "goal": plan.goal,
            "duration_weeks": plan.duration_weeks,
            "weekly_frequency": plan.weekly_frequency,
            "status": str(plan.status.value) if hasattr(plan.status, "value") else str(plan.status),
            "source": str(plan.source.value) if hasattr(plan.source, "value") else str(plan.source),
            "version": plan.version,
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
            "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
            "days": [
                {
                    "id": str(d.id),
                    "day_index": d.day_index,
                    "title": d.title,
                    "notes": d.notes,
                    "exercises": [
                        {
                            "id": str(pe.id),
                            "exercise_id": str(pe.exercise_id),
                            "exercise_name": pe.exercise.name if pe.exercise else "Unknown",
                            "primary_muscle": pe.exercise.primary_muscle if pe.exercise else "",
                            "equipment": str(pe.exercise.equipment.value) if pe.exercise and pe.exercise.equipment else "",
                            "order_index": pe.order_index,
                            "sets": pe.sets,
                            "reps_min": pe.reps_min,
                            "reps_max": pe.reps_max,
                            "rest_seconds": pe.rest_seconds,
                            "target_rpe": pe.target_rpe,
                            "notes": pe.notes,
                        }
                        for pe in (d.planned_exercises or [])
                    ],
                }
                for d in (plan.training_days or [])
            ],
        }


# ── Domain exceptions ───────────────────────────────────────────────────────

class UserNotFoundError(Exception):
    def __init__(self, user_id):
        self.user_id = user_id
        super().__init__(f"User not found: {user_id}")


class ProfileNotFoundError(Exception):
    def __init__(self, user_id):
        self.user_id = user_id
        super().__init__(f"Fitness profile not found for user: {user_id}")


class NoCandidateExercisesError(Exception):
    def __init__(self, user_id, profile):
        self.user_id = user_id
        self.equipment = profile.available_equipment
        super().__init__(f"No candidate exercises for user={user_id} with equipment={self.equipment}")


class PlanGenerationError(Exception):
    pass


class ValidationFailedError(Exception):
    pass


class PlanSaveError(Exception):
    pass
