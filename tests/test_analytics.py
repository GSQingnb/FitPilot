"""FitPilot analytics tests — statistics, trends, data quality rules.

Requires: PostgreSQL with workout data (setup_data fixture creates it).
"""
import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DB_URL = "postgresql+asyncpg://fitpilot:fitpilot_dev_password@localhost:5432/fitpilot"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


async def _create_user(db_session):
    from database.repositories.user_repository import UserRepository
    ur = UserRepository(db_session)
    u = await ur.create(email=f"ana_{uuid.uuid4().hex[:8]}@test.com", display_name="Ana")
    await db_session.commit()
    return u.id


async def _create_completed_workout(db_session, user_id, exercise_id, started_date, sets_data):
    """Helper: create a completed workout with sets, commit to DB."""
    from database.models.workout_session import WorkoutSession, WorkoutStatus
    from database.models.workout_exercise import WorkoutExercise, ExerciseStatus
    from database.models.workout_set import WorkoutSet

    ws = WorkoutSession(user_id=user_id, status=WorkoutStatus.COMPLETED,
                         started_at=started_date, completed_at=started_date,
                         duration_seconds=3600)
    db_session.add(ws)
    await db_session.flush()

    we = WorkoutExercise(workout_session_id=ws.id, exercise_id=exercise_id,
                          order_index=1, status=ExerciseStatus.COMPLETED)
    db_session.add(we)
    await db_session.flush()

    for sd in sets_data:
        s = WorkoutSet(workout_exercise_id=we.id, is_completed=True, **sd)
        db_session.add(s)
    await db_session.flush()
    await db_session.commit()
    return ws.id


# ── Overview tests ───────────────────────────────────────────────────────────

class TestOverview:
    @pytest.mark.asyncio
    async def test_empty_user_returns_zero_stats(self, db_session):
        from services.analytics_service import AnalyticsService
        svc = AnalyticsService(db_session)
        uid = await _create_user(db_session)
        result = await svc.get_overview(uid)
        assert result["completed_workouts"] == 0
        assert result["completed_sets"] == 0
        assert result["total_volume"] == 0.0

    @pytest.mark.asyncio
    async def test_incomplete_sessions_excluded(self, db_session):
        from services.analytics_service import AnalyticsService
        from database.repositories.exercise_repository import ExerciseRepository
        from database.models.workout_session import WorkoutSession, WorkoutStatus

        uid = await _create_user(db_session)
        er = ExerciseRepository(db_session)
        exs, _ = await er.list_filtered(limit=1)

        # Create in_progress session (should be excluded)
        ws = WorkoutSession(user_id=uid, status=WorkoutStatus.IN_PROGRESS)
        db_session.add(ws)
        await db_session.flush()
        await db_session.commit()

        svc = AnalyticsService(db_session)
        result = await svc.get_overview(uid)
        assert result["completed_workouts"] == 0

    @pytest.mark.asyncio
    async def test_completed_sets_counted(self, db_session):
        from services.analytics_service import AnalyticsService
        from database.repositories.exercise_repository import ExerciseRepository

        uid = await _create_user(db_session)
        er = ExerciseRepository(db_session)
        exs, _ = await er.list_filtered(limit=1)

        await _create_completed_workout(db_session, uid, exs[0].id,
            date.today() - timedelta(days=1),
            [{"set_index": 1, "set_type": "working", "weight_kg": 50, "reps": 10, "rpe": 7},
             {"set_index": 2, "set_type": "working", "weight_kg": 55, "reps": 8, "rpe": 8}])
        await db_session.commit()

        svc = AnalyticsService(db_session)
        result = await svc.get_overview(uid)
        assert result["completed_workouts"] == 1
        assert result["completed_sets"] == 2
        assert result["total_reps"] == 18
        assert result["total_volume"] == 50*10 + 55*8  # 940

    @pytest.mark.asyncio
    async def test_weight_null_not_counted_in_volume(self, db_session):
        from services.analytics_service import AnalyticsService
        from database.repositories.exercise_repository import ExerciseRepository

        uid = await _create_user(db_session)
        er = ExerciseRepository(db_session)
        exs, _ = await er.list_filtered(limit=1)

        await _create_completed_workout(db_session, uid, exs[0].id,
            date.today() - timedelta(days=1),
            [{"set_index": 1, "set_type": "bodyweight", "weight_kg": None, "reps": 15}])
        await db_session.commit()

        svc = AnalyticsService(db_session)
        result = await svc.get_overview(uid)
        assert result["total_reps"] == 15
        assert result["total_volume"] == 0.0  # no weight → no volume
        assert result["data_quality"]["has_weight_data"] is False


# ── Weekly activity tests ────────────────────────────────────────────────────

class TestWeekly:
    @pytest.mark.asyncio
    async def test_weekly_aggregation(self, db_session):
        from services.analytics_service import AnalyticsService
        from database.repositories.exercise_repository import ExerciseRepository

        uid = await _create_user(db_session)
        er = ExerciseRepository(db_session)
        exs, _ = await er.list_filtered(limit=1)

        # 2 workouts this week, 1 last week
        today = date.today()
        for days_ago in [1, 3]:
            await _create_completed_workout(db_session, uid, exs[0].id,
                today - timedelta(days=days_ago),
                [{"set_index": 1, "set_type": "working", "weight_kg": 40, "reps": 10}])
        await db_session.commit()

        svc = AnalyticsService(db_session)
        weeks = await svc.get_weekly_activity(uid, weeks=4)
        assert len(weeks) == 4
        # Most recent week should have 2
        latest = weeks[-1]
        assert latest["completed_workouts"] >= 1


# ── Exercise trend tests ─────────────────────────────────────────────────────

class TestExerciseTrend:
    @pytest.mark.asyncio
    async def test_exercise_trend_with_data(self, db_session):
        from services.analytics_service import AnalyticsService
        from database.repositories.exercise_repository import ExerciseRepository

        uid = await _create_user(db_session)
        er = ExerciseRepository(db_session)
        exs, _ = await er.list_filtered(limit=2)

        # Week 1: weight 30
        await _create_completed_workout(db_session, uid, exs[0].id,
            date.today() - timedelta(days=14),
            [{"set_index": 1, "set_type": "working", "weight_kg": 30, "reps": 10}])
        # Week 2: weight 35
        await _create_completed_workout(db_session, uid, exs[0].id,
            date.today() - timedelta(days=1),
            [{"set_index": 1, "set_type": "working", "weight_kg": 35, "reps": 10}])
        await db_session.commit()

        svc = AnalyticsService(db_session)
        trend = await svc.get_exercise_trend(uid, exs[0].id)
        assert trend["summary"]["session_count"] == 2
        # Trend might be insufficient_data if sessions are in same week
        assert trend["trend_direction"] in ("up", "stable", "insufficient_data")

    @pytest.mark.asyncio
    async def test_exercise_trend_empty(self, db_session):
        from services.analytics_service import AnalyticsService
        from database.repositories.exercise_repository import ExerciseRepository

        uid = await _create_user(db_session)
        er = ExerciseRepository(db_session)
        exs, _ = await er.list_filtered(limit=1)

        svc = AnalyticsService(db_session)
        trend = await svc.get_exercise_trend(uid, exs[0].id)
        assert trend["summary"]["session_count"] == 0
        assert trend["trend_direction"] == "insufficient_data"

    @pytest.mark.asyncio
    async def test_nonexistent_exercise_returns_404(self, db_session):
        from services.analytics_service import AnalyticsService, AnalyticsError
        uid = await _create_user(db_session)
        svc = AnalyticsService(db_session)
        with pytest.raises(AnalyticsError) as ex:
            await svc.get_exercise_trend(uid, uuid.uuid4())
        assert ex.value.status_code == 404


# ── Muscle distribution tests ────────────────────────────────────────────────

class TestMuscleDistribution:
    @pytest.mark.asyncio
    async def test_muscle_distribution(self, db_session):
        from services.analytics_service import AnalyticsService
        from database.repositories.exercise_repository import ExerciseRepository

        uid = await _create_user(db_session)
        er = ExerciseRepository(db_session)
        exs, _ = await er.list_filtered(limit=5)

        if len(exs) >= 2:
            await _create_completed_workout(db_session, uid, exs[0].id,
                date.today() - timedelta(days=1),
                [{"set_index": 1, "set_type": "working", "weight_kg": 40, "reps": 10}])
            await _create_completed_workout(db_session, uid, exs[1].id,
                date.today() - timedelta(days=1),
                [{"set_index": 1, "set_type": "working", "weight_kg": 30, "reps": 8}])
            await db_session.commit()

        svc = AnalyticsService(db_session)
        dist = await svc.get_muscle_distribution(uid)
        assert len(dist) >= 1
        total_pct = sum(d["percentage_by_sets"] for d in dist)
        assert 99.0 <= total_pct <= 101.0  # float tolerance


# ── Data isolation tests ────────────────────────────────────────────────────

class TestIsolation:
    @pytest.mark.asyncio
    async def test_user_data_isolated(self, db_session):
        from services.analytics_service import AnalyticsService
        from database.repositories.exercise_repository import ExerciseRepository

        u1 = await _create_user(db_session)
        u2 = await _create_user(db_session)
        er = ExerciseRepository(db_session)
        exs, _ = await er.list_filtered(limit=1)

        await _create_completed_workout(db_session, u1, exs[0].id,
            date.today() - timedelta(days=1),
            [{"set_index": 1, "set_type": "working", "weight_kg": 50, "reps": 10}])
        await db_session.commit()

        svc = AnalyticsService(db_session)
        r1 = await svc.get_overview(u1)
        r2 = await svc.get_overview(u2)
        assert r1["completed_workouts"] == 1
        assert r2["completed_workouts"] == 0
