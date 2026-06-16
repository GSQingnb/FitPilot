"""Workout API routes — start, track, complete, cancel, history."""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.database import get_db
from api.schemas import (
    WorkoutStartRequest,
    WorkoutCompleteRequest,
    WorkoutCancelRequest,
    WorkoutSetCreate,
    WorkoutSetUpdate,
    WorkoutSetResponse,
    WorkoutSessionDetailResponse,
    WorkoutSessionListResponse,
    WorkoutExerciseStatusRequest,
)
from services.workout_service import WorkoutService, WorkoutError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["workouts"])


@router.post(
    "/users/{user_id}/workouts/start",
    response_model=WorkoutSessionDetailResponse,
    status_code=201,
)
async def start_workout(
    user_id: uuid.UUID,
    body: WorkoutStartRequest,
    db: AsyncSession = Depends(get_db),
):
    """Start a workout from an active training plan. Copies planned exercises as workout exercises."""
    svc = WorkoutService(db)
    try:
        return await svc.start_workout(
            user_id=user_id,
            training_plan_id=body.training_plan_id,
            training_day_id=body.training_day_id,
        )
    except WorkoutError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get(
    "/users/{user_id}/workouts/current",
    response_model=Optional[WorkoutSessionDetailResponse],
)
async def get_current_workout(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get user's current in-progress workout, or null."""
    svc = WorkoutService(db)
    result = await svc.get_current(user_id)
    return result


@router.post(
    "/workouts/{session_id}/exercises/{exercise_id}/start",
    response_model=dict,
)
async def start_exercise(
    session_id: uuid.UUID,
    exercise_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Mark an exercise as started."""
    svc = WorkoutService(db)
    try:
        return await svc.start_exercise(session_id, exercise_id)
    except WorkoutError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post(
    "/workouts/{session_id}/exercises/{exercise_id}/complete",
    response_model=dict,
)
async def complete_exercise(
    session_id: uuid.UUID,
    exercise_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Mark an exercise as completed."""
    svc = WorkoutService(db)
    try:
        return await svc.complete_exercise(session_id, exercise_id)
    except WorkoutError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post(
    "/workouts/{session_id}/exercises/{exercise_id}/skip",
    response_model=dict,
)
async def skip_exercise(
    session_id: uuid.UUID,
    exercise_id: uuid.UUID,
    body: WorkoutExerciseStatusRequest = WorkoutExerciseStatusRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Skip an exercise with an optional reason."""
    svc = WorkoutService(db)
    try:
        return await svc.skip_exercise(session_id, exercise_id, reason=body.reason)
    except WorkoutError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post(
    "/workouts/{session_id}/exercises/{exercise_id}/sets",
    response_model=WorkoutSetResponse,
    status_code=201,
)
async def add_set(
    session_id: uuid.UUID,
    exercise_id: uuid.UUID,
    body: WorkoutSetCreate,
    db: AsyncSession = Depends(get_db),
):
    """Record a set for an exercise in the workout."""
    svc = WorkoutService(db)
    try:
        return await svc.add_set(session_id, exercise_id, body.model_dump(exclude_none=False))
    except WorkoutError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.put(
    "/workouts/{session_id}/sets/{set_id}",
    response_model=WorkoutSetResponse,
)
async def update_set(
    session_id: uuid.UUID,
    set_id: uuid.UUID,
    body: WorkoutSetUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a recorded set (only when session is in_progress)."""
    svc = WorkoutService(db)
    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        return await svc.update_set(session_id, set_id, update_data)
    except WorkoutError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.delete(
    "/workouts/{session_id}/sets/{set_id}",
    status_code=204,
)
async def delete_set(
    session_id: uuid.UUID,
    set_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a recorded set (only when session is in_progress)."""
    svc = WorkoutService(db)
    try:
        await svc.delete_set(session_id, set_id)
    except WorkoutError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post(
    "/workouts/{session_id}/complete",
    response_model=WorkoutSessionDetailResponse,
)
async def complete_workout(
    session_id: uuid.UUID,
    body: WorkoutCompleteRequest = WorkoutCompleteRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Complete a workout. Requires at least one completed set."""
    svc = WorkoutService(db)
    try:
        return await svc.complete_session(
            session_id,
            notes=body.notes,
            perceived_difficulty=body.perceived_difficulty,
        )
    except WorkoutError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post(
    "/workouts/{session_id}/cancel",
    response_model=dict,
)
async def cancel_workout(
    session_id: uuid.UUID,
    body: WorkoutCancelRequest = WorkoutCancelRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a workout. Preserves recorded sets."""
    svc = WorkoutService(db)
    try:
        return await svc.cancel_session(session_id, reason=body.reason)
    except WorkoutError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get(
    "/users/{user_id}/workouts",
    response_model=WorkoutSessionListResponse,
)
async def list_workouts(
    user_id: uuid.UUID,
    status: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None, alias="date_from"),
    date_to: Optional[datetime] = Query(None, alias="date_to"),
    training_plan_id: Optional[uuid.UUID] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List user's workout history with optional filters."""
    svc = WorkoutService(db)
    filters = {}
    if status:
        filters["status"] = status
    if date_from:
        filters["date_from"] = date_from
    if date_to:
        filters["date_to"] = date_to
    if training_plan_id:
        filters["training_plan_id"] = training_plan_id
    items, total = await svc.list_sessions(user_id, limit=limit, offset=offset, **filters)
    return WorkoutSessionListResponse(total=total, limit=limit, offset=offset, items=items)


@router.get(
    "/users/{user_id}/workouts/{session_id}",
    response_model=WorkoutSessionDetailResponse,
)
async def get_workout_detail(
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get full workout session details with exercises and sets."""
    svc = WorkoutService(db)
    try:
        return await svc.get_session(user_id, session_id)
    except WorkoutError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
