"""Analytics repository — pure SQL aggregation for workout statistics.

All queries filter to completed sessions and completed sets only.
"""
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.workout_session import WorkoutSession, WorkoutStatus
from database.models.workout_exercise import WorkoutExercise
from database.models.workout_set import WorkoutSet
from database.models.exercise import Exercise


class AnalyticsRepository:
    """Pure SQL aggregation for performance analytics."""

    def __init__(self, session: AsyncSession):
        self._session = session

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _completed_session_filter(self, user_id: uuid.UUID, date_from: Optional[date] = None,
                                   date_to: Optional[date] = None):
        conditions = [
            WorkoutSession.user_id == user_id,
            WorkoutSession.status == WorkoutStatus.COMPLETED,
        ]
        if date_from:
            conditions.append(WorkoutSession.started_at >= date_from)
        if date_to:
            conditions.append(WorkoutSession.started_at <= date_to)
        return and_(*conditions)

    # ── Overview ────────────────────────────────────────────────────────────

    async def get_overview(self, user_id: uuid.UUID, date_from: date, date_to: date) -> dict:
        base = self._completed_session_filter(user_id, date_from, date_to)

        # Count sessions
        session_count = await self._session.scalar(
            select(func.count(WorkoutSession.id)).where(base)
        ) or 0

        if session_count == 0:
            return self._empty_overview(date_from, date_to)

        # Duration stats
        duration_stats = await self._session.execute(
            select(
                func.coalesce(func.sum(WorkoutSession.duration_seconds), 0),
                func.coalesce(func.avg(WorkoutSession.duration_seconds), 0),
            ).where(base, WorkoutSession.duration_seconds.isnot(None))
        )
        total_dur, avg_dur = duration_stats.first()

        # Set/reps/volume from completed sets
        set_stats = await self._session.execute(
            select(
                func.count(WorkoutSet.id),
                func.coalesce(func.sum(WorkoutSet.reps), 0),
                func.coalesce(func.sum(WorkoutSet.weight_kg * WorkoutSet.reps), 0.0),
                func.coalesce(func.avg(WorkoutSet.rpe), None),
            ).select_from(WorkoutSet).join(WorkoutExercise).join(
                WorkoutSession, WorkoutExercise.workout_session_id == WorkoutSession.id
            ).where(
                base, WorkoutSet.is_completed == True,
            )
        )
        sets_count, total_reps, total_volume, avg_rpe = set_stats.first()

        has_weight = await self._session.scalar(
            select(func.count(WorkoutSet.id)).select_from(WorkoutSet).join(WorkoutExercise).join(
                WorkoutSession, WorkoutExercise.workout_session_id == WorkoutSession.id
            ).where(
                base, WorkoutSet.is_completed == True,
                WorkoutSet.weight_kg.isnot(None),
            )
        ) or 0

        # Streaks
        streak_data = await self._calculate_streaks(user_id, date_to)

        return {
            "period": {"start": date_from.isoformat(), "end": date_to.isoformat()},
            "completed_workouts": session_count,
            "total_duration_seconds": int(total_dur),
            "average_duration_seconds": round(float(avg_dur), 0) if avg_dur else 0,
            "completed_sets": sets_count,
            "total_reps": int(total_reps),
            "total_volume": round(float(total_volume), 1),
            "average_rpe": round(float(avg_rpe), 1) if avg_rpe else None,
            "current_streak_days": streak_data["current"],
            "longest_streak_days": streak_data["longest"],
            "data_quality": {
                "has_weight_data": has_weight > 0,
                "has_rpe_data": avg_rpe is not None,
            },
        }

    async def _calculate_streaks(self, user_id: uuid.UUID, up_to: date) -> dict:
        """Calculate current and longest consecutive training day streaks."""
        result = await self._session.execute(
            select(
                func.distinct(func.date(WorkoutSession.started_at))
            ).where(
                WorkoutSession.user_id == user_id,
                WorkoutSession.status == WorkoutStatus.COMPLETED,
                WorkoutSession.started_at <= up_to,
            ).order_by(func.date(WorkoutSession.started_at).desc())
        )
        dates = [row[0] for row in result.fetchall()]

        if not dates:
            return {"current": 0, "longest": 0}

        current = 1
        longest = 1
        streak = 1
        today = up_to
        checking_current = True

        for i in range(1, len(dates)):
            prev = dates[i - 1]
            curr = dates[i]
            diff = (prev - curr).days

            if diff == 1:
                streak += 1
            else:
                if checking_current and dates[0] != today and (today - dates[0]).days > 1:
                    current = 0
                    checking_current = False
                streak = 1 if not checking_current else streak
            longest = max(longest, streak)

        if dates[0] != today and (today - dates[0]).days > 1:
            current = 0

        return {"current": current, "longest": longest}

    def _empty_overview(self, date_from: date, date_to: date) -> dict:
        return {
            "period": {"start": date_from.isoformat(), "end": date_to.isoformat()},
            "completed_workouts": 0,
            "total_duration_seconds": 0,
            "average_duration_seconds": 0,
            "completed_sets": 0,
            "total_reps": 0,
            "total_volume": 0.0,
            "average_rpe": None,
            "current_streak_days": 0,
            "longest_streak_days": 0,
            "data_quality": {"has_weight_data": False, "has_rpe_data": False},
        }

    # ── Weekly activity ─────────────────────────────────────────────────────

    async def get_weekly_activity(self, user_id: uuid.UUID, weeks: int = 8) -> List[dict]:
        end = date.today()
        start = end - date.resolution * (weeks * 7 - 1)
        rows = []
        cursor = start
        while cursor <= end:
            week_start = cursor
            week_end = cursor + date.resolution * 6
            week_data = await self._week_aggregate(user_id, week_start, week_end)
            week_data["week_start"] = week_start.isoformat()
            rows.append(week_data)
            cursor = week_end + date.resolution
        return rows

    async def _week_aggregate(self, user_id: uuid.UUID, start: date, end: date) -> dict:
        base = self._completed_session_filter(user_id, start, end)

        count = await self._session.scalar(
            select(func.count(WorkoutSession.id)).where(base)
        ) or 0

        dur = await self._session.scalar(
            select(func.coalesce(func.sum(WorkoutSession.duration_seconds), 0))
            .where(base, WorkoutSession.duration_seconds.isnot(None))
        ) or 0

        if count == 0:
            return {"completed_workouts": 0, "completed_sets": 0, "total_reps": 0,
                    "total_volume": 0.0, "average_rpe": None, "total_duration_seconds": 0}

        sets_data = await self._session.execute(
            select(
                func.count(WorkoutSet.id),
                func.coalesce(func.sum(WorkoutSet.reps), 0),
                func.coalesce(func.sum(WorkoutSet.weight_kg * WorkoutSet.reps), 0.0),
                func.coalesce(func.avg(WorkoutSet.rpe), None),
            ).select_from(WorkoutSet).join(WorkoutExercise).join(
                WorkoutSession, WorkoutExercise.workout_session_id == WorkoutSession.id
            ).where(
                base, WorkoutSet.is_completed == True,
            )
        )
        sc, tr, tv, ar = sets_data.first()

        return {
            "completed_workouts": count,
            "completed_sets": sc,
            "total_reps": int(tr),
            "total_volume": round(float(tv), 1),
            "average_rpe": round(float(ar), 1) if ar else None,
            "total_duration_seconds": int(dur),
        }

    # ── Exercise trend ───────────────────────────────────────────────────────

    async def get_exercise_summary(self, user_id: uuid.UUID, exercise_id: uuid.UUID,
                                    date_from: Optional[date] = None,
                                    date_to: Optional[date] = None) -> dict:
        base = self._completed_session_filter(user_id, date_from, date_to)

        stats = await self._session.execute(
            select(
                func.count(func.distinct(WorkoutSession.id)),
                func.count(WorkoutSet.id),
                func.coalesce(func.sum(WorkoutSet.reps), 0),
                func.coalesce(func.sum(WorkoutSet.weight_kg * WorkoutSet.reps), 0.0),
                func.coalesce(func.max(WorkoutSet.weight_kg), None),
                func.coalesce(func.max(WorkoutSet.reps), None),
                func.coalesce(func.avg(WorkoutSet.rpe), None),
                func.coalesce(func.max(WorkoutSession.started_at), None),
            ).select_from(WorkoutSet).join(WorkoutExercise).join(
                WorkoutSession, WorkoutExercise.workout_session_id == WorkoutSession.id
            ).where(
                base, WorkoutExercise.exercise_id == exercise_id,
                WorkoutSet.is_completed == True,
            )
        )
        sc, sc2, tr, tv, mw, br, ar, la = stats.first()

        return {
            "session_count": sc,
            "completed_set_count": sc2,
            "total_reps": int(tr),
            "total_volume": round(float(tv), 1),
            "max_weight": round(float(mw), 1) if mw else None,
            "best_set_reps": br,
            "average_rpe": round(float(ar), 1) if ar else None,
            "last_performed_at": la.isoformat() if la else None,
        }

    async def get_exercise_trend(self, user_id: uuid.UUID, exercise_id: uuid.UUID,
                                  date_from: Optional[date] = None,
                                  date_to: Optional[date] = None) -> List[dict]:
        base = self._completed_session_filter(user_id, date_from, date_to)

        weeks = await self._session.execute(
            select(
                func.date_trunc("week", WorkoutSession.started_at).label("week"),
            ).where(base).distinct().order_by("week")
        )
        week_list = [row[0] for row in weeks.fetchall()]

        result = []
        for week_start in week_list:
            week_end_val = week_start + date.resolution * 6
            week_filter = self._completed_session_filter(user_id, week_start, week_end_val)

            pts = await self._session.execute(
                select(
                    func.count(WorkoutSet.id),
                    func.coalesce(func.sum(WorkoutSet.reps), 0),
                    func.coalesce(func.sum(WorkoutSet.weight_kg * WorkoutSet.reps), 0.0),
                    func.coalesce(func.max(WorkoutSet.weight_kg), None),
                    func.coalesce(func.avg(WorkoutSet.rpe), None),
                ).select_from(WorkoutSet).join(WorkoutExercise).join(
                    WorkoutSession, WorkoutExercise.workout_session_id == WorkoutSession.id
                ).where(
                    week_filter, WorkoutExercise.exercise_id == exercise_id,
                    WorkoutSet.is_completed == True,
                )
            )
            sc1, tr1, tv1, mw1, ar1 = pts.first()
            if sc1 > 0:
                result.append({
                    "date": week_start.isoformat(),
                    "max_weight": round(float(mw1), 1) if mw1 else None,
                    "total_volume": round(float(tv1), 1),
                    "total_reps": int(tr1),
                    "average_rpe": round(float(ar1), 1) if ar1 else None,
                })
        return result

    # ── Muscle distribution ──────────────────────────────────────────────────

    async def get_muscle_distribution(self, user_id: uuid.UUID, date_from: Optional[date] = None,
                                       date_to: Optional[date] = None) -> List[dict]:
        base = self._completed_session_filter(user_id, date_from, date_to)

        rows = await self._session.execute(
            select(
                Exercise.primary_muscle,
                func.count(WorkoutSet.id).label("sets"),
                func.coalesce(func.sum(WorkoutSet.reps), 0).label("reps"),
                func.coalesce(func.sum(WorkoutSet.weight_kg * WorkoutSet.reps), 0.0).label("volume"),
            ).select_from(WorkoutSet)
            .join(WorkoutExercise, WorkoutSet.workout_exercise_id == WorkoutExercise.id)
            .join(WorkoutSession, WorkoutExercise.workout_session_id == WorkoutSession.id)
            .join(Exercise, WorkoutExercise.exercise_id == Exercise.id)
            .where(base, WorkoutSet.is_completed == True)
            .group_by(Exercise.primary_muscle)
            .order_by(func.count(WorkoutSet.id).desc())
        )

        total_sets = 0
        entries = []
        for row in rows.fetchall():
            entries.append({
                "primary_muscle": row[0],
                "completed_sets": row[1],
                "total_reps": int(row[2]),
                "total_volume": round(float(row[3]), 1),
            })
            total_sets += row[1]

        for e in entries:
            e["percentage_by_sets"] = round(e["completed_sets"] / total_sets * 100, 1) if total_sets else 0.0

        return entries

    # ── Period metrics for reports ───────────────────────────────────────────

    async def get_period_metrics(self, user_id: uuid.UUID, period_start: date, period_end: date) -> dict:
        ov = await self.get_overview(user_id, period_start, period_end)
        prev_start = period_start - (period_end - period_start)
        prev_end = period_start - date.resolution
        prev = await self.get_overview(user_id, prev_start, prev_end)
        return {
            "current": ov,
            "previous": prev if prev["completed_workouts"] > 0 else None,
        }
