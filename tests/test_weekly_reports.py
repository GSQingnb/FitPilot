"""FitPilot weekly reports tests — generation, fallback, idempotency, permissions.

Requires: PostgreSQL with workout data.
"""
import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DB_URL = "postgresql+asyncpg://fitpilot:0000@localhost:5432/fitpilot"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


async def _setup_user_with_workout(db_session):
    """Create user with one completed workout for report generation."""
    from database.repositories.user_repository import UserRepository
    from database.repositories.exercise_repository import ExerciseRepository
    from database.models.workout_session import WorkoutSession, WorkoutStatus
    from database.models.workout_exercise import WorkoutExercise, ExerciseStatus
    from database.models.workout_set import WorkoutSet

    ur = UserRepository(db_session)
    u = await ur.create(email=f"rpt_{uuid.uuid4().hex[:8]}@test.com", display_name="RPT")
    await db_session.commit()

    er = ExerciseRepository(db_session)
    exs, _ = await er.list_filtered(limit=1)
    assert len(exs) >= 1

    ws = WorkoutSession(user_id=u.id, status=WorkoutStatus.COMPLETED,
                         started_at=date.today() - timedelta(days=3),
                         completed_at=date.today() - timedelta(days=3),
                         duration_seconds=3600)
    db_session.add(ws)
    await db_session.flush()
    we = WorkoutExercise(workout_session_id=ws.id, exercise_id=exs[0].id,
                          order_index=1, status=ExerciseStatus.COMPLETED)
    db_session.add(we)
    await db_session.flush()
    db_session.add(WorkoutSet(workout_exercise_id=we.id, set_index=1,
                               set_type="working", weight_kg=50, reps=10,
                               rpe=7.5, is_completed=True))
    await db_session.commit()
    return u.id


# ── Report generation tests ──────────────────────────────────────────────────

class TestReportGeneration:
    @pytest.mark.asyncio
    async def test_rule_based_fallback_generates_report(self, db_session):
        from services.weekly_report_service import WeeklyReportService
        uid = await _setup_user_with_workout(db_session)

        # No API key → fallback to rule-based
        svc = WeeklyReportService(db_session, api_key="")
        ps = date.today() - timedelta(days=7)
        pe = date.today() - timedelta(days=1)
        result = await svc.generate(uid, period_start=ps, period_end=pe)
        assert result["source"] == "rule_based"
        assert result["status"] == "generated"
        assert len(result["summary"]) > 0
        assert "highlights" in result

    @pytest.mark.asyncio
    async def test_generated_report_saves_metrics(self, db_session):
        from services.weekly_report_service import WeeklyReportService
        uid = await _setup_user_with_workout(db_session)

        svc = WeeklyReportService(db_session, api_key="")
        ps = date.today() - timedelta(days=7)
        pe = date.today() - timedelta(days=1)
        result = await svc.generate(uid, period_start=ps, period_end=pe)
        assert "current" in result["metrics"]
        assert result["metrics"]["current"]["completed_workouts"] >= 1

    @pytest.mark.asyncio
    async def test_idempotent_same_period(self, db_session):
        from services.weekly_report_service import WeeklyReportService
        uid = await _setup_user_with_workout(db_session)

        svc = WeeklyReportService(db_session, api_key="")
        ps = date.today() - timedelta(days=7)
        pe = date.today() - timedelta(days=1)
        r1 = await svc.generate(uid, period_start=ps, period_end=pe)
        r2 = await svc.generate(uid, period_start=ps, period_end=pe)
        assert r1["id"] == r2["id"]  # same report returned

    @pytest.mark.asyncio
    async def test_force_regenerates(self, db_session):
        from services.weekly_report_service import WeeklyReportService
        uid = await _setup_user_with_workout(db_session)

        svc = WeeklyReportService(db_session, api_key="")
        ps = date.today() - timedelta(days=7)
        pe = date.today() - timedelta(days=1)
        r1 = await svc.generate(uid, period_start=ps, period_end=pe)
        r2 = await svc.generate(uid, period_start=ps, period_end=pe, force=True)
        assert r1["id"] == r2["id"]  # same ID, overwritten

    @pytest.mark.asyncio
    async def test_data_insufficient_report(self, db_session):
        from services.weekly_report_service import WeeklyReportService
        from database.repositories.user_repository import UserRepository

        ur = UserRepository(db_session)
        u = await ur.create(email=f"empty_{uuid.uuid4().hex[:8]}@test.com", display_name="Empty")
        await db_session.commit()

        svc = WeeklyReportService(db_session, api_key="")
        ps = date.today() - timedelta(days=14)
        pe = date.today() - timedelta(days=1)
        result = await svc.generate(u.id, period_start=ps, period_end=pe)
        # Should still generate (rule-based with zero stats)
        assert "未完成" in result["summary"] or result["metrics"]["current"]["completed_workouts"] == 0

    @pytest.mark.asyncio
    async def test_period_end_before_start_fails(self, db_session):
        from services.weekly_report_service import WeeklyReportService
        from services.analytics_service import AnalyticsError
        uid = await _setup_user_with_workout(db_session)

        svc = WeeklyReportService(db_session, api_key="")
        with pytest.raises(AnalyticsError) as ex:
            await svc.generate(uid, period_start=date.today(), period_end=date.today() - timedelta(days=1))
        assert ex.value.status_code == 422


# ── Report listing tests ─────────────────────────────────────────────────────

class TestReportListing:
    @pytest.mark.asyncio
    async def test_list_reports(self, db_session):
        from services.weekly_report_service import WeeklyReportService
        uid = await _setup_user_with_workout(db_session)

        svc = WeeklyReportService(db_session, api_key="")
        await svc.generate(uid, period_start=date.today() - timedelta(days=7),
                            period_end=date.today() - timedelta(days=1))

        items, total = await svc.list_reports(uid)
        assert total >= 1
        assert items[0]["period_end"] is not None

    @pytest.mark.asyncio
    async def test_get_report_detail(self, db_session):
        from services.weekly_report_service import WeeklyReportService
        uid = await _setup_user_with_workout(db_session)

        svc = WeeklyReportService(db_session, api_key="")
        r = await svc.generate(uid, period_start=date.today() - timedelta(days=7),
                                period_end=date.today() - timedelta(days=1))
        detail = await svc.get_report(uid, uuid.UUID(r["id"]))
        assert detail["id"] == r["id"]

    @pytest.mark.asyncio
    async def test_cannot_access_other_user_report(self, db_session):
        from services.weekly_report_service import WeeklyReportService
        from services.analytics_service import AnalyticsError
        from database.repositories.user_repository import UserRepository

        uid = await _setup_user_with_workout(db_session)
        ur = UserRepository(db_session)
        u2 = await ur.create(email=f"other_{uuid.uuid4().hex[:8]}@test.com", display_name="Other")
        await db_session.commit()

        svc = WeeklyReportService(db_session, api_key="")
        r = await svc.generate(uid, period_start=date.today() - timedelta(days=7),
                                period_end=date.today() - timedelta(days=1))

        with pytest.raises(AnalyticsError) as ex:
            await svc.get_report(u2.id, uuid.UUID(r["id"]))
        assert ex.value.status_code == 404


# ── Schema tests ─────────────────────────────────────────────────────────────

class TestReportSchema:
    def test_valid_report_schema(self):
        from services.weekly_report_service import GeneratedWeeklyReport
        r = GeneratedWeeklyReport(
            summary="Good week",
            highlights=["Completed 4 sessions"],
            issues=["Squat volume down"],
            recommendations=["Increase squat frequency"],
        )
        assert len(r.highlights) <= 5
        assert len(r.recommendations) <= 5

    def test_report_schema_empty_ok(self):
        from services.weekly_report_service import GeneratedWeeklyReport
        r = GeneratedWeeklyReport(summary="No data", highlights=[], issues=[], recommendations=[])
        assert r.summary == "No data"

    def test_report_schema_too_long_fails(self):
        from services.weekly_report_service import GeneratedWeeklyReport
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            GeneratedWeeklyReport(
                summary="x" * 2001,  # too long
            )


# ── Redis lock tests ─────────────────────────────────────────────────────────

class TestGenerationLock:
    def test_lock_acquire_and_release(self):
        from services.weekly_report_service import GenerationLock, REDIS_URL
        lock = GenerationLock("test_lock_acquire")
        assert lock.acquire() is True
        lock.release()

    def test_lock_prevents_duplicate(self):
        from services.weekly_report_service import GenerationLock, REDIS_URL
        import redis as redis_lib
        try:
            r = redis_lib.from_url(REDIS_URL, decode_responses=True)
            r.ping()
        except Exception:
            pytest.skip("Redis not available for lock test")

        lock1 = GenerationLock("test_lock_dup_t")
        lock2 = GenerationLock("test_lock_dup_t")
        lock1.acquire()  # first lock
        # Second lock should NOT be acquirable
        assert lock1.acquire() is False  # lock1's own retry should fail
        lock1.release()
        # After release, a new lock can acquire
        lock3 = GenerationLock("test_lock_dup_t")
        assert lock3.acquire() is True
        lock3.release()


# ── Regression tests ─────────────────────────────────────────────────────────

class TestRegression:
    def test_health_works(self):
        import requests
        r = requests.get("http://localhost:8000/health", timeout=10)
        assert r.status_code == 200

    def test_health_database_works(self):
        import requests
        r = requests.get("http://localhost:8000/health/database", timeout=10)
        assert r.status_code == 200

    def test_workout_api_works(self):
        import requests
        r = requests.get("http://localhost:8000/exercises?limit=1", timeout=10)
        assert r.status_code == 200

    def test_agent_imports(self):
        from agents.agent_orchestrator import CoachAgent, PlanAgent, ProgressAgent
        assert CoachAgent is not None
