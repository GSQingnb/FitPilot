"""FitPilot workout execution tests — models, repository, service, API.

Requires: PostgreSQL with all migrations applied, exercises seeded.
"""
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import text
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


@pytest_asyncio.fixture
async def setup_data(db_session):
    """Create user + profile + active plan with exercises for workout testing."""
    from database.repositories.user_repository import UserRepository
    from database.repositories.fitness_profile_repository import FitnessProfileRepository
    from database.repositories.exercise_repository import ExerciseRepository
    from database.repositories.training_plan_repository import TrainingPlanRepository

    ur = UserRepository(db_session)
    user = await ur.create(email=f"wktest_{uuid.uuid4().hex[:8]}@test.com", display_name="WorkoutTest")
    await db_session.commit()

    fpr = FitnessProfileRepository(db_session)
    await fpr.upsert(user_id=user.id, goal="muscle_gain", experience_level="beginner",
                     weekly_frequency=3, session_duration_minutes=60,
                     available_equipment=["dumbbell", "bodyweight"],
                     target_muscles=["chest", "back"], excluded_exercises=[], limitations=None)
    await db_session.commit()

    er = ExerciseRepository(db_session)
    exs, _ = await er.list_filtered(limit=3)
    assert len(exs) >= 2

    plan_repo = TrainingPlanRepository(db_session)
    plan = await plan_repo.create_plan_tree(
        user_id=user.id, name="Test Plan", goal="muscle_gain",
        duration_weeks=4, weekly_frequency=2, overview="",
        days_data=[
            {"day_index": 1, "title": "Upper",
             "exercises": [
                 {"exercise_id": str(exs[0].id), "order_index": 1, "sets": 3,
                  "reps_min": 8, "reps_max": 12, "rest_seconds": 90, "target_rpe": 7.5},
                 {"exercise_id": str(exs[1].id), "order_index": 2, "sets": 3,
                  "reps_min": 10, "reps_max": 15, "rest_seconds": 60},
             ]},
            {"day_index": 2, "title": "Lower",
             "exercises": [
                 {"exercise_id": str(exs[2].id), "order_index": 1, "sets": 4,
                  "reps_min": 8, "reps_max": 10, "rest_seconds": 120},
             ]},
        ],
    )
    # Activate plan
    await plan_repo.activate_for_user(plan.id, user.id)
    await db_session.commit()

    plan = await plan_repo.get_by_id(plan.id)
    day1 = plan.training_days[0]

    return {"user_id": user.id, "plan_id": plan.id, "day_id": day1.id, "exercises": exs}


# ── Migration tests ──────────────────────────────────────────────────────────

class TestMigration:
    @pytest.mark.asyncio
    async def test_tables_exist(self, db_session):
        """Verify 3 workout tables exist."""
        result = await db_session.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        )
        tables = {row[0] for row in result.fetchall()}
        for t in ("workout_sessions", "workout_exercises", "workout_sets"):
            assert t in tables, f"Missing table: {t}"

    @pytest.mark.asyncio
    async def test_enum_types_exist(self, db_session):
        """Verify enum types are created."""
        result = await db_session.execute(
            text("SELECT typname FROM pg_type WHERE typname IN "
                 "('workout_status_enum','exercise_status_enum','set_type_enum')")
        )
        types = {row[0] for row in result.fetchall()}
        assert "workout_status_enum" in types
        assert "exercise_status_enum" in types
        assert "set_type_enum" in types


# ── Start workout tests ─────────────────────────────────────────────────────

class TestStartWorkout:
    @pytest.mark.asyncio
    async def test_start_from_active_plan(self, db_session, setup_data):
        from services.workout_service import WorkoutService
        svc = WorkoutService(db_session)
        result = await svc.start_workout(
            setup_data["user_id"], setup_data["plan_id"], setup_data["day_id"]
        )
        assert result["status"] == "in_progress"
        assert result["training_plan_id"] == str(setup_data["plan_id"])
        assert len(result["exercises"]) == 2

    @pytest.mark.asyncio
    async def test_duplicate_start_returns_409(self, db_session, setup_data):
        from services.workout_service import WorkoutService, WorkoutError
        svc = WorkoutService(db_session)
        await svc.start_workout(setup_data["user_id"], setup_data["plan_id"], setup_data["day_id"])
        with pytest.raises(WorkoutError) as exc:
            await svc.start_workout(setup_data["user_id"], setup_data["plan_id"], setup_data["day_id"])
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_wrong_user_cannot_start(self, db_session, setup_data):
        from services.workout_service import WorkoutService, WorkoutError
        svc = WorkoutService(db_session)
        with pytest.raises(WorkoutError) as exc:
            await svc.start_workout(uuid.uuid4(), setup_data["plan_id"], setup_data["day_id"])
        assert exc.value.status_code == 404


# ── Set CRUD tests ──────────────────────────────────────────────────────────

class TestSetCRUD:
    @pytest.mark.asyncio
    async def test_add_set(self, db_session, setup_data):
        from services.workout_service import WorkoutService
        svc = WorkoutService(db_session)
        result = await svc.start_workout(setup_data["user_id"], setup_data["plan_id"], setup_data["day_id"])
        exs = result["exercises"]
        assert len(exs) > 0
        eid = exs[0]["id"]
        sid = result["id"]

        wset = await svc.add_set(sid, uuid.UUID(eid), {
            "set_index": 1, "set_type": "working",
            "weight_kg": 20.0, "reps": 10, "rpe": 7.5,
        })
        assert wset["set_index"] == 1
        assert wset["reps"] == 10

    @pytest.mark.asyncio
    async def test_add_set_without_data_fails(self, db_session, setup_data):
        from services.workout_service import WorkoutService, WorkoutError
        svc = WorkoutService(db_session)
        result = await svc.start_workout(setup_data["user_id"], setup_data["plan_id"], setup_data["day_id"])
        eid = result["exercises"][0]["id"]
        with pytest.raises(WorkoutError) as exc:
            await svc.add_set(result["id"], uuid.UUID(eid), {"set_index": 1, "set_type": "working"})
        assert exc.value.status_code == 422

    @pytest.mark.asyncio
    async def test_duplicate_set_index_returns_409(self, db_session, setup_data):
        from services.workout_service import WorkoutService, WorkoutError
        svc = WorkoutService(db_session)
        result = await svc.start_workout(setup_data["user_id"], setup_data["plan_id"], setup_data["day_id"])
        eid = result["exercises"][0]["id"]
        sid = result["id"]

        await svc.add_set(sid, uuid.UUID(eid), {"set_index": 1, "set_type": "working", "reps": 10})
        with pytest.raises(WorkoutError) as exc:
            await svc.add_set(sid, uuid.UUID(eid), {"set_index": 1, "set_type": "working", "reps": 10})
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    async def test_update_set(self, db_session, setup_data):
        from services.workout_service import WorkoutService
        svc = WorkoutService(db_session)
        result = await svc.start_workout(setup_data["user_id"], setup_data["plan_id"], setup_data["day_id"])
        eid = result["exercises"][0]["id"]
        sid = result["id"]

        wset = await svc.add_set(sid, uuid.UUID(eid), {"set_index": 1, "set_type": "working", "reps": 10})
        updated = await svc.update_set(sid, uuid.UUID(wset["id"]), {"reps": 12, "weight_kg": 25.0})
        assert updated["reps"] == 12

    @pytest.mark.asyncio
    async def test_delete_set(self, db_session, setup_data):
        from services.workout_service import WorkoutService
        svc = WorkoutService(db_session)
        result = await svc.start_workout(setup_data["user_id"], setup_data["plan_id"], setup_data["day_id"])
        eid = result["exercises"][0]["id"]
        sid = result["id"]

        wset = await svc.add_set(sid, uuid.UUID(eid), {"set_index": 1, "set_type": "working", "reps": 10})
        await svc.delete_set(sid, uuid.UUID(wset["id"]))
        # Verify deleted
        from database.repositories.workout_repository import WorkoutRepository
        repo = WorkoutRepository(db_session)
        assert await repo.get_set(uuid.UUID(wset["id"])) is None

    @pytest.mark.asyncio
    async def test_cannot_modify_set_after_complete(self, db_session, setup_data):
        from services.workout_service import WorkoutService, WorkoutError
        svc = WorkoutService(db_session)
        result = await svc.start_workout(setup_data["user_id"], setup_data["plan_id"], setup_data["day_id"])
        eid = result["exercises"][0]["id"]
        sid = result["id"]

        wset = await svc.add_set(sid, uuid.UUID(eid), {"set_index": 1, "set_type": "working", "reps": 10})
        await svc.complete_session(sid)

        with pytest.raises(WorkoutError) as exc:
            await svc.add_set(sid, uuid.UUID(eid), {"set_index": 2, "set_type": "working", "reps": 8})
        assert exc.value.status_code == 409


# ── Exercise state machine tests ─────────────────────────────────────────────

class TestExerciseState:
    @pytest.mark.asyncio
    async def test_start_exercise(self, db_session, setup_data):
        from services.workout_service import WorkoutService
        svc = WorkoutService(db_session)
        result = await svc.start_workout(setup_data["user_id"], setup_data["plan_id"], setup_data["day_id"])
        eid = result["exercises"][0]["id"]
        ex = await svc.start_exercise(result["id"], uuid.UUID(eid))
        assert ex["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_skip_exercise(self, db_session, setup_data):
        from services.workout_service import WorkoutService
        svc = WorkoutService(db_session)
        result = await svc.start_workout(setup_data["user_id"], setup_data["plan_id"], setup_data["day_id"])
        eid = result["exercises"][1]["id"]
        ex = await svc.skip_exercise(result["id"], uuid.UUID(eid), reason="equipment busy")
        assert ex["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_cannot_skip_completed(self, db_session, setup_data):
        from services.workout_service import WorkoutService, WorkoutError
        svc = WorkoutService(db_session)
        result = await svc.start_workout(setup_data["user_id"], setup_data["plan_id"], setup_data["day_id"])
        eid = result["exercises"][0]["id"]
        sid = result["id"]

        await svc.complete_exercise(sid, uuid.UUID(eid))
        with pytest.raises(WorkoutError) as exc:
            await svc.skip_exercise(sid, uuid.UUID(eid))
        assert exc.value.status_code == 409


# ── Complete / Cancel tests ──────────────────────────────────────────────────

class TestCompleteCancel:
    @pytest.mark.asyncio
    async def test_complete_session(self, db_session, setup_data):
        from services.workout_service import WorkoutService
        svc = WorkoutService(db_session)
        result = await svc.start_workout(setup_data["user_id"], setup_data["plan_id"], setup_data["day_id"])
        eid = result["exercises"][0]["id"]
        sid = result["id"]

        await svc.add_set(sid, uuid.UUID(eid), {"set_index": 1, "set_type": "working", "weight_kg": 20.0, "reps": 10})
        await svc.add_set(sid, uuid.UUID(eid), {"set_index": 2, "set_type": "working", "weight_kg": 20.0, "reps": 10})
        await svc.add_set(sid, uuid.UUID(eid), {"set_index": 3, "set_type": "working", "weight_kg": 20.0, "reps": 8})

        completed = await svc.complete_session(sid, notes="Great workout", perceived_difficulty=7.5)
        assert completed["status"] == "completed"
        assert completed["duration_seconds"] is not None
        assert completed["stats"]["total_volume"] > 0

    @pytest.mark.asyncio
    async def test_cannot_complete_without_sets(self, db_session, setup_data):
        from services.workout_service import WorkoutService, WorkoutError
        svc = WorkoutService(db_session)
        result = await svc.start_workout(setup_data["user_id"], setup_data["plan_id"], setup_data["day_id"])
        with pytest.raises(WorkoutError) as exc:
            await svc.complete_session(result["id"])
        assert exc.value.status_code == 422

    @pytest.mark.asyncio
    async def test_cancel_session(self, db_session, setup_data):
        from services.workout_service import WorkoutService
        svc = WorkoutService(db_session)
        result = await svc.start_workout(setup_data["user_id"], setup_data["plan_id"], setup_data["day_id"])
        cancelled = await svc.cancel_session(result["id"])
        assert cancelled["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cannot_cancel_completed(self, db_session, setup_data):
        from services.workout_service import WorkoutService, WorkoutError
        svc = WorkoutService(db_session)
        result = await svc.start_workout(setup_data["user_id"], setup_data["plan_id"], setup_data["day_id"])
        eid = result["exercises"][0]["id"]
        await svc.add_set(result["id"], uuid.UUID(eid), {"set_index": 1, "set_type": "working", "reps": 10})
        await svc.complete_session(result["id"])
        with pytest.raises(WorkoutError) as exc:
            await svc.cancel_session(result["id"])
        assert exc.value.status_code == 409


# ── History tests ────────────────────────────────────────────────────────────

class TestHistory:
    @pytest.mark.asyncio
    async def test_current_workout(self, db_session, setup_data):
        from services.workout_service import WorkoutService
        svc = WorkoutService(db_session)
        await svc.start_workout(setup_data["user_id"], setup_data["plan_id"], setup_data["day_id"])
        current = await svc.get_current(setup_data["user_id"])
        assert current is not None
        assert current["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_list_workouts(self, db_session, setup_data):
        from services.workout_service import WorkoutService
        svc = WorkoutService(db_session)
        result = await svc.start_workout(setup_data["user_id"], setup_data["plan_id"], setup_data["day_id"])
        eid = result["exercises"][0]["id"]
        await svc.add_set(result["id"], uuid.UUID(eid), {"set_index": 1, "set_type": "working", "reps": 10})
        await svc.complete_session(result["id"])

        items, total = await svc.list_sessions(setup_data["user_id"])
        assert total >= 1

        items, total = await svc.list_sessions(setup_data["user_id"], status="completed")
        assert total >= 1

    @pytest.mark.asyncio
    async def test_get_detail(self, db_session, setup_data):
        from services.workout_service import WorkoutService
        svc = WorkoutService(db_session)
        result = await svc.start_workout(setup_data["user_id"], setup_data["plan_id"], setup_data["day_id"])
        detail = await svc.get_session(setup_data["user_id"], uuid.UUID(result["id"]))
        assert detail["stats"] is not None

    @pytest.mark.asyncio
    async def test_cannot_see_other_user_workout(self, db_session, setup_data):
        from services.workout_service import WorkoutService, WorkoutError
        svc = WorkoutService(db_session)
        result = await svc.start_workout(setup_data["user_id"], setup_data["plan_id"], setup_data["day_id"])
        with pytest.raises(WorkoutError) as exc:
            await svc.get_session(uuid.uuid4(), uuid.UUID(result["id"]))
        assert exc.value.status_code == 404


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

    def test_training_plans_api_works(self):
        import requests
        # Just verify the endpoints exist
        r = requests.get("http://localhost:8000/exercises?limit=1", timeout=10)
        assert r.status_code == 200

    def test_agent_modules_import(self):
        from agents.agent_orchestrator import CoachAgent, PlanAgent
        from core.intent_recognizer import IntentRecognizer
        assert CoachAgent is not None
        assert PlanAgent is not None
