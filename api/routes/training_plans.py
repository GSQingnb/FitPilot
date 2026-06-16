"""Training plan API routes — generation, query, activation, archive."""
import logging
import os
import uuid
from typing import Optional

import redis
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.database import get_db
from api.schemas import (
    TrainingPlanGenerateRequest,
    TrainingPlanDetailResponse,
    TrainingPlanListResponse,
    TrainingPlanSummaryResponse,
)
from database.repositories.training_plan_repository import TrainingPlanRepository
from services.training_plan_service import (
    TrainingPlanService,
    UserNotFoundError,
    ProfileNotFoundError,
    NoCandidateExercisesError,
    PlanGenerationError,
    ValidationFailedError,
    PlanSaveError,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["training-plans"])

# Redis lock for plan generation dedup
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_LOCK_TTL = 120  # seconds — matches LLM timeout


def _acquire_generation_lock(user_id: uuid.UUID) -> bool:
    """Try to acquire a generation lock. Returns True if acquired, False if already locked."""
    try:
        r = redis.from_url(REDIS_URL, decode_responses=True)
        key = f"plan_generation:{user_id}"
        # SET NX (only if not exists) with TTL
        acquired = r.set(key, "1", nx=True, ex=_LOCK_TTL)
        return bool(acquired)
    except Exception:
        # If Redis is down, allow the request (degraded mode)
        logger.warning("Redis unavailable, skipping generation lock")
        return True


def _release_generation_lock(user_id: uuid.UUID):
    try:
        r = redis.from_url(REDIS_URL, decode_responses=True)
        r.delete(f"plan_generation:{user_id}")
    except Exception:
        pass


def _get_llm_config():
    return {
        "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "base_url": os.getenv("ANTHROPIC_BASE_URL", "").strip() or None,
        "model": os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
    }


@router.post(
    "/users/{user_id}/training-plans/generate",
    response_model=TrainingPlanDetailResponse,
    status_code=201,
)
async def generate_plan(
    user_id: uuid.UUID,
    body: TrainingPlanGenerateRequest = TrainingPlanGenerateRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Generate a structured AI training plan based on user profile.

    Requires: user exists, fitness profile exists, exercise library populated.
    Uses Redis lock to prevent duplicate submissions.
    """
    # Dedup lock
    if not _acquire_generation_lock(user_id):
        raise HTTPException(status_code=409, detail="A plan generation is already in progress for this user")

    try:
        llm_cfg = _get_llm_config()
        if not llm_cfg["api_key"]:
            raise HTTPException(status_code=503, detail="LLM service not configured")

        service = TrainingPlanService(db=db, **llm_cfg)
        result = await service.generate_plan(
            user_id=user_id,
            duration_weeks=body.duration_weeks,
            plan_name=body.name,
            additional_preferences=body.additional_preferences,
        )
        return result
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found")
    except ProfileNotFoundError:
        raise HTTPException(status_code=409, detail="User does not have a fitness profile")
    except NoCandidateExercisesError as e:
        raise HTTPException(status_code=422, detail=f"No exercises match user equipment: {e.equipment}")
    except ValidationFailedError as e:
        raise HTTPException(status_code=422, detail=f"Plan validation failed: {e}")
    except PlanGenerationError as e:
        raise HTTPException(status_code=502, detail=f"Plan generation failed: {e}")
    except PlanSaveError as e:
        raise HTTPException(status_code=500, detail=f"Failed to save plan: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error generating plan for user={user_id}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        _release_generation_lock(user_id)


@router.get(
    "/users/{user_id}/training-plans",
    response_model=TrainingPlanListResponse,
)
async def list_plans(
    user_id: uuid.UUID,
    status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List training plans for a user, optionally filtered by status."""
    repo = TrainingPlanRepository(db)
    plans, total = await repo.list_by_user(user_id=user_id, status=status, limit=limit, offset=offset)
    items = [TrainingPlanSummaryResponse.model_validate(p) for p in plans]
    return TrainingPlanListResponse(total=total, limit=limit, offset=offset, items=items)


@router.get(
    "/training-plans/{plan_id}",
    response_model=TrainingPlanDetailResponse,
)
async def get_plan(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get full plan details including days and exercises."""
    repo = TrainingPlanRepository(db)
    plan = await repo.get_by_id(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return _plan_to_detail(plan)


@router.post(
    "/users/{user_id}/training-plans/{plan_id}/activate",
    response_model=TrainingPlanDetailResponse,
)
async def activate_plan(
    user_id: uuid.UUID,
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Activate a plan. Archives all other active plans for this user."""
    repo = TrainingPlanRepository(db)
    # Verify ownership
    plan = await repo.get_by_id_for_user(plan_id, user_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found for this user")

    try:
        activated = await repo.activate_for_user(plan_id, user_id)
        await db.commit()
        return _plan_to_detail(activated)
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to activate plan {plan_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to activate plan")


@router.post(
    "/users/{user_id}/training-plans/{plan_id}/archive",
    response_model=TrainingPlanDetailResponse,
)
async def archive_plan(
    user_id: uuid.UUID,
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Archive a plan. Idempotent: can be called on already-archived plans."""
    repo = TrainingPlanRepository(db)
    plan = await repo.get_by_id_for_user(plan_id, user_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found for this user")

    try:
        archived = await repo.archive_for_user(plan_id, user_id)
        await db.commit()
        return _plan_to_detail(archived)
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to archive plan {plan_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to archive plan")


def _plan_to_detail(plan) -> dict:
    """Convert ORM plan tree to detail response dict."""
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
