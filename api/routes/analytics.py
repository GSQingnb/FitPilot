"""Analytics API routes — training statistics, trends, and muscle distribution."""
import uuid
import logging
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.database import get_db
from api.schemas import (
    AnalyticsOverviewResponse,
    WeeklyAnalyticsPoint,
    ExerciseTrendResponse,
    MuscleDistributionItem,
)
from services.analytics_service import AnalyticsService, AnalyticsError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users/{user_id}/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOverviewResponse)
async def get_overview(
    user_id: uuid.UUID,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get training overview statistics. Defaults to last 28 days."""
    svc = AnalyticsService(db)
    try:
        return await svc.get_overview(user_id, date_from=date_from, date_to=date_to)
    except AnalyticsError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/weekly", response_model=List[WeeklyAnalyticsPoint])
async def get_weekly(
    user_id: uuid.UUID,
    weeks: int = Query(8, ge=1, le=52),
    db: AsyncSession = Depends(get_db),
):
    """Get weekly aggregated training data."""
    svc = AnalyticsService(db)
    try:
        return await svc.get_weekly_activity(user_id, weeks=weeks)
    except AnalyticsError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/exercises/{exercise_id}", response_model=ExerciseTrendResponse)
async def get_exercise_trend(
    user_id: uuid.UUID,
    exercise_id: uuid.UUID,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get performance trend for a specific exercise."""
    svc = AnalyticsService(db)
    try:
        return await svc.get_exercise_trend(user_id, exercise_id, date_from=date_from, date_to=date_to)
    except AnalyticsError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/muscles", response_model=List[MuscleDistributionItem])
async def get_muscle_distribution(
    user_id: uuid.UUID,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get training distribution by muscle group."""
    svc = AnalyticsService(db)
    try:
        return await svc.get_muscle_distribution(user_id, date_from=date_from, date_to=date_to)
    except AnalyticsError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
