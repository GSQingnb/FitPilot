"""Analytics service — interprets SQL aggregations and determines trends."""
import uuid
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database.repositories.analytics_repository import AnalyticsRepository
from database.repositories.user_repository import UserRepository
from database.repositories.exercise_repository import ExerciseRepository


class AnalyticsService:
    """Computes training statistics and trend directions."""

    TREND_THRESHOLD = 0.05  # 5% change threshold for stable vs up/down

    def __init__(self, db: AsyncSession):
        self._db = db
        self._user_repo = UserRepository(db)
        self._exercise_repo = ExerciseRepository(db)
        self._analytics_repo = AnalyticsRepository(db)

    async def get_overview(self, user_id: uuid.UUID, date_from: Optional[date] = None,
                           date_to: Optional[date] = None) -> dict:
        await self._verify_user(user_id)
        if date_from is None:
            date_from = date.today() - timedelta(days=27)
        if date_to is None:
            date_to = date.today()
        return await self._analytics_repo.get_overview(user_id, date_from, date_to)

    async def get_weekly_activity(self, user_id: uuid.UUID, weeks: int = 8) -> List[dict]:
        await self._verify_user(user_id)
        weeks = max(1, min(weeks, 52))
        return await self._analytics_repo.get_weekly_activity(user_id, weeks)

    async def get_exercise_trend(self, user_id: uuid.UUID, exercise_id: uuid.UUID,
                                  date_from: Optional[date] = None,
                                  date_to: Optional[date] = None) -> dict:
        await self._verify_user(user_id)
        ex = await self._exercise_repo.get_by_id(exercise_id)
        if not ex:
            raise AnalyticsError("Exercise not found", 404)

        summary = await self._analytics_repo.get_exercise_summary(user_id, exercise_id, date_from, date_to)
        trend = await self._analytics_repo.get_exercise_trend(user_id, exercise_id, date_from, date_to)

        direction = self._compute_trend_direction(trend, "total_volume")
        if summary["session_count"] == 0:
            direction = "insufficient_data"

        return {
            "exercise": {"id": str(exercise_id), "name": ex.name},
            "summary": summary,
            "trend": trend,
            "trend_direction": direction,
        }

    async def get_muscle_distribution(self, user_id: uuid.UUID, date_from: Optional[date] = None,
                                       date_to: Optional[date] = None) -> List[dict]:
        await self._verify_user(user_id)
        return await self._analytics_repo.get_muscle_distribution(user_id, date_from, date_to)

    async def get_period_metrics(self, user_id: uuid.UUID, period_start: date, period_end: date) -> dict:
        await self._verify_user(user_id)
        return await self._analytics_repo.get_period_metrics(user_id, period_start, period_end)

    # ── Trend logic ──────────────────────────────────────────────────────────

    def _compute_trend_direction(self, trend_data: List[dict], metric: str) -> str:
        if len(trend_data) < 2:
            return "insufficient_data"
        values = [d.get(metric) for d in trend_data if d.get(metric) is not None]
        if len(values) < 2:
            return "insufficient_data"
        first, last = values[0], values[-1]
        if first == 0:
            return "up" if last > 0 else "insufficient_data"
        change = abs(last - first) / first
        if change < self.TREND_THRESHOLD:
            return "stable"
        return "up" if last > first else "down"

    async def _verify_user(self, user_id: uuid.UUID):
        if not await self._user_repo.get_by_id(user_id):
            raise AnalyticsError("User not found", 404)


class AnalyticsError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)
