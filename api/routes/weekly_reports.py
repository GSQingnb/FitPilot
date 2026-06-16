"""Weekly report API routes — AI/rule-based training period summaries."""
import os
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.database import get_db
from api.schemas import (
    WeeklyReportGenerateRequest,
    WeeklyReportResponse,
    WeeklyReportListResponse,
)
from services.weekly_report_service import WeeklyReportService
from services.analytics_service import AnalyticsError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users/{user_id}/weekly-reports", tags=["weekly-reports"])


def _get_llm_config():
    return {
        "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "base_url": os.getenv("ANTHROPIC_BASE_URL", "").strip() or None,
        "model": os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
    }


@router.post("/generate", response_model=WeeklyReportResponse)
async def generate_report(
    user_id: uuid.UUID,
    body: WeeklyReportGenerateRequest = WeeklyReportGenerateRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Generate a weekly training report. Uses AI when available, falls back to rule-based."""
    llm_cfg = _get_llm_config()
    svc = WeeklyReportService(db, **llm_cfg)
    try:
        result = await svc.generate(
            user_id=user_id,
            period_start=body.period_start,
            period_end=body.period_end,
            force=body.force,
        )
        return result
    except AnalyticsError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("", response_model=WeeklyReportListResponse)
async def list_reports(
    user_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List user's weekly reports, ordered by period_end descending."""
    svc = WeeklyReportService(db)
    items, total = await svc.list_reports(user_id, limit=limit, offset=offset)
    return WeeklyReportListResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/{report_id}", response_model=WeeklyReportResponse)
async def get_report(
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific report detail. Report must belong to user."""
    svc = WeeklyReportService(db)
    try:
        return await svc.get_report(user_id, report_id)
    except AnalyticsError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
