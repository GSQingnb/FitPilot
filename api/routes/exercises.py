"""Exercise API routes."""
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.database import get_db
from api.schemas import ExerciseResponse, ExerciseListResponse
from database.repositories.exercise_repository import ExerciseRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/exercises", tags=["exercises"])


@router.get("", response_model=ExerciseListResponse)
async def list_exercises(
    primary_muscle: Optional[str] = Query(None),
    equipment: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    movement_pattern: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Fuzzy name search"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List exercises with optional filtering and pagination. Only active exercises."""
    repo = ExerciseRepository(db)
    exercises, total = await repo.list_filtered(
        primary_muscle=primary_muscle,
        equipment=equipment,
        difficulty=difficulty,
        movement_pattern=movement_pattern,
        search=search,
        limit=limit,
        offset=offset,
    )
    return ExerciseListResponse(
        total=total,
        limit=limit,
        offset=offset,
        exercises=[ExerciseResponse.model_validate(e) for e in exercises],
    )


@router.get("/{exercise_id}", response_model=ExerciseResponse)
async def get_exercise(
    exercise_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single exercise by ID. Returns 404 if not found or inactive."""
    repo = ExerciseRepository(db)
    exercise = await repo.get_by_id(exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return exercise
