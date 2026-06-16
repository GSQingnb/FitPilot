"""FitPilot training plan tests — schema, validation, repository, API.

Requires: PostgreSQL running with test data (exercises seeded).
Uses mock LLM to avoid real API calls.
"""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

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


# ── Schema validation tests ──────────────────────────────────────────────────

class TestGeneratedPlanSchema:
    def test_valid_plan_passes(self):
        from services.plan_generation_service import GeneratedPlan
        plan = GeneratedPlan(
            name="Test Plan",
            goal="muscle_gain",
            duration_weeks=4,
            weekly_frequency=3,
            overview="Test",
            days=[
                {
                    "day_index": 1, "title": "Day 1",
                    "exercises": [
                        {
                            "exercise_id": str(uuid.uuid4()),
                            "exercise_name": "Push Up",
                            "order_index": 1, "sets": 3,
                            "reps_min": 8, "reps_max": 12,
                            "rest_seconds": 90, "target_rpe": 7.5,
                        }
                    ]
                }
            ],
        )
        assert plan.name == "Test Plan"

    def test_reps_max_less_than_min_fails(self):
        from services.plan_generation_service import GeneratedPlan
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            GeneratedPlan(
                name="Test", goal="muscle_gain", duration_weeks=4, weekly_frequency=1, overview="",
                days=[{
                    "day_index": 1, "title": "D1",
                    "exercises": [{
                        "exercise_id": str(uuid.uuid4()), "exercise_name": "Push Up",
                        "order_index": 1, "sets": 3, "reps_min": 12, "reps_max": 8,
                        "rest_seconds": 90,
                    }]
                }],
            )

    def test_target_rpe_out_of_range_fails(self):
        from services.plan_generation_service import GeneratedPlan
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            GeneratedPlan(
                name="Test", goal="muscle_gain", duration_weeks=4, weekly_frequency=1, overview="",
                days=[{
                    "day_index": 1, "title": "D1",
                    "exercises": [{
                        "exercise_id": str(uuid.uuid4()), "exercise_name": "Push Up",
                        "order_index": 1, "sets": 3, "reps_min": 8, "reps_max": 12,
                        "rest_seconds": 90, "target_rpe": 11.0,
                    }]
                }],
            )

    def test_empty_days_fails(self):
        from services.plan_generation_service import GeneratedPlan
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            GeneratedPlan(
                name="Test", goal="muscle_gain", duration_weeks=4, weekly_frequency=1,
                overview="", days=[],
            )


# ── Validation service tests ────────────────────────────────────────────────

class TestValidationService:
    @pytest.mark.asyncio
    async def test_valid_plan_passes_validation(self, db_session):
        from services.plan_validation_service import PlanValidationService
        from database.repositories.exercise_repository import ExerciseRepository

        profile = MagicMock()
        profile.experience_level = "beginner"
        profile.weekly_frequency = 2
        profile.available_equipment = ["dumbbell", "bodyweight"]
        profile.excluded_exercises = []
        profile.target_muscles = []

        repo = ExerciseRepository(db_session)
        exercises, _ = await repo.list_filtered(equipment="dumbbell", limit=5)
        if len(exercises) < 3:
            pytest.skip("Need at least 3 dumbbell exercises")
        bodyweight, _ = await repo.list_filtered(equipment="bodyweight", limit=2)

        candidates = exercises[:3] + bodyweight[:1]

        plan = {
            "name": "Test Plan",
            "goal": "muscle_gain",
            "duration_weeks": 4,
            "weekly_frequency": 2,
            "overview": "A test",
            "days": [
                {
                    "day_index": 1, "title": "Upper",
                    "exercises": [
                        {"exercise_id": str(candidates[0].id), "exercise_name": candidates[0].name,
                         "order_index": 1, "sets": 3, "reps_min": 8, "reps_max": 12,
                         "rest_seconds": 90, "target_rpe": 7.5},
                        {"exercise_id": str(candidates[1].id), "exercise_name": candidates[1].name,
                         "order_index": 2, "sets": 3, "reps_min": 10, "reps_max": 15,
                         "rest_seconds": 60, "target_rpe": None},
                    ],
                },
                {
                    "day_index": 2, "title": "Lower",
                    "exercises": [
                        {"exercise_id": str(candidates[2].id), "exercise_name": candidates[2].name,
                         "order_index": 1, "sets": 3, "reps_min": 8, "reps_max": 12,
                         "rest_seconds": 90, "target_rpe": 8.0},
                    ],
                },
            ],
        }

        svc = PlanValidationService()
        result = svc.validate_plan(plan, profile, candidates)
        assert result.is_valid, f"Errors: {[str(e) for e in result.errors]}"

    @pytest.mark.asyncio
    async def test_nonexistent_exercise_id_fails(self, db_session):
        from services.plan_validation_service import PlanValidationService
        from database.repositories.exercise_repository import ExerciseRepository

        profile = MagicMock()
        profile.experience_level = "intermediate"
        profile.weekly_frequency = 1
        profile.available_equipment = ["dumbbell"]
        profile.excluded_exercises = []

        repo = ExerciseRepository(db_session)
        candidates, _ = await repo.list_filtered(equipment="dumbbell", limit=2)

        plan = {
            "name": "Bad Plan", "goal": "muscle_gain",
            "duration_weeks": 4, "weekly_frequency": 1, "overview": "",
            "days": [{
                "day_index": 1, "title": "D1",
                "exercises": [{
                    "exercise_id": str(uuid.uuid4()),
                    "exercise_name": "Fake Exercise",
                    "order_index": 1, "sets": 3,
                    "reps_min": 8, "reps_max": 12,
                    "rest_seconds": 90,
                }],
            }],
        }

        svc = PlanValidationService()
        result = svc.validate_plan(plan, profile, candidates)
        assert not result.is_valid

    @pytest.mark.asyncio
    async def test_wrong_equipment_fails(self, db_session):
        from services.plan_validation_service import PlanValidationService
        from database.repositories.exercise_repository import ExerciseRepository

        profile = MagicMock()
        profile.experience_level = "intermediate"
        profile.weekly_frequency = 1
        profile.available_equipment = ["bodyweight"]
        profile.excluded_exercises = []

        repo = ExerciseRepository(db_session)
        candidates, _ = await repo.list_filtered(equipment="barbell", limit=1)
        if not candidates:
            pytest.skip("Need barbell exercise")

        plan = {
            "name": "Bad Plan", "goal": "muscle_gain",
            "duration_weeks": 4, "weekly_frequency": 1, "overview": "",
            "days": [{
                "day_index": 1, "title": "D1",
                "exercises": [{
                    "exercise_id": str(candidates[0].id),
                    "exercise_name": candidates[0].name,
                    "order_index": 1, "sets": 3,
                    "reps_min": 8, "reps_max": 12,
                    "rest_seconds": 90,
                }],
            }],
        }

        svc = PlanValidationService()
        result = svc.validate_plan(plan, profile, candidates)
        assert not result.is_valid

    @pytest.mark.asyncio
    async def test_duplicate_day_index_fails(self, db_session):
        from services.plan_validation_service import PlanValidationService
        from database.repositories.exercise_repository import ExerciseRepository

        profile = MagicMock()
        profile.experience_level = "intermediate"
        profile.weekly_frequency = 2
        profile.available_equipment = ["dumbbell"]
        profile.excluded_exercises = []

        repo = ExerciseRepository(db_session)
        candidates, _ = await repo.list_filtered(equipment="dumbbell", limit=3)

        def mk_ex(i, name):
            return {"exercise_id": str(candidates[i].id), "exercise_name": name,
                    "order_index": 1, "sets": 3, "reps_min": 8, "reps_max": 12, "rest_seconds": 90}

        plan = {
            "name": "Bad", "goal": "muscle_gain",
            "duration_weeks": 4, "weekly_frequency": 2, "overview": "",
            "days": [
                {"day_index": 1, "title": "D1", "exercises": [mk_ex(0, candidates[0].name)]},
                {"day_index": 1, "title": "D1 Dup", "exercises": [mk_ex(1, candidates[1].name)]},
            ],
        }

        svc = PlanValidationService()
        result = svc.validate_plan(plan, profile, candidates[:2])
        assert not result.is_valid

    @pytest.mark.asyncio
    async def test_too_many_exercises_beginner_fails(self, db_session):
        from services.plan_validation_service import PlanValidationService
        from database.repositories.exercise_repository import ExerciseRepository

        profile = MagicMock()
        profile.experience_level = "beginner"
        profile.weekly_frequency = 1
        profile.available_equipment = ["dumbbell"]
        profile.excluded_exercises = []

        repo = ExerciseRepository(db_session)
        candidates, _ = await repo.list_filtered(equipment="dumbbell", limit=10)
        if len(candidates) < 7:
            pytest.skip("Need at least 7 dumbbell exercises")

        exercises = [{"exercise_id": str(candidates[i].id), "exercise_name": candidates[i].name,
                       "order_index": i+1, "sets": 3, "reps_min": 8, "reps_max": 12, "rest_seconds": 90}
                      for i in range(7)]

        plan = {
            "name": "Too Many", "goal": "muscle_gain",
            "duration_weeks": 4, "weekly_frequency": 1, "overview": "",
            "days": [{"day_index": 1, "title": "D1", "exercises": exercises}],
        }

        svc = PlanValidationService()
        result = svc.validate_plan(plan, profile, candidates)
        assert not result.is_valid


# ── Repository tests ─────────────────────────────────────────────────────────

class TestTrainingPlanRepository:
    @pytest.mark.asyncio
    async def test_create_plan_tree(self, db_session):
        from database.repositories.user_repository import UserRepository
        from database.repositories.exercise_repository import ExerciseRepository
        from database.repositories.training_plan_repository import TrainingPlanRepository

        ur = UserRepository(db_session)
        user = await ur.create(email=f"tpr_{uuid.uuid4().hex[:8]}@test.com", display_name="TPR")
        await db_session.commit()

        er = ExerciseRepository(db_session)
        exs, _ = await er.list_filtered(limit=3)
        assert len(exs) >= 3

        repo = TrainingPlanRepository(db_session)
        plan = await repo.create_plan_tree(
            user_id=user.id,
            name="Test Plan Tree",
            goal="muscle_gain",
            duration_weeks=4,
            weekly_frequency=2,
            overview="Test overview",
            days_data=[
                {
                    "day_index": 1, "title": "Upper",
                    "exercises": [
                        {"exercise_id": str(exs[0].id), "order_index": 1,
                         "sets": 3, "reps_min": 8, "reps_max": 12, "rest_seconds": 90, "target_rpe": 7.5},
                        {"exercise_id": str(exs[1].id), "order_index": 2,
                         "sets": 3, "reps_min": 10, "reps_max": 15, "rest_seconds": 60},
                    ],
                },
                {
                    "day_index": 2, "title": "Lower",
                    "exercises": [
                        {"exercise_id": str(exs[2].id), "order_index": 1,
                         "sets": 4, "reps_min": 8, "reps_max": 10, "rest_seconds": 120},
                    ],
                },
            ],
        )
        await db_session.commit()

        loaded = await repo.get_by_id(plan.id)
        assert loaded is not None
        assert loaded.name == "Test Plan Tree"
        assert loaded.version == 1
        assert len(loaded.training_days) == 2
        assert len(loaded.training_days[0].planned_exercises) == 2
        assert len(loaded.training_days[1].planned_exercises) == 1

    @pytest.mark.asyncio
    async def test_version_increments(self, db_session):
        from database.repositories.user_repository import UserRepository
        from database.repositories.exercise_repository import ExerciseRepository
        from database.repositories.training_plan_repository import TrainingPlanRepository

        ur = UserRepository(db_session)
        user = await ur.create(email=f"ver_{uuid.uuid4().hex[:8]}@test.com", display_name="Ver")
        await db_session.commit()

        er = ExerciseRepository(db_session)
        exs, _ = await er.list_filtered(limit=1)

        repo = TrainingPlanRepository(db_session)
        day1 = [{"day_index":1,"title":"D1","exercises":[{"exercise_id":str(exs[0].id),"order_index":1,"sets":3,"reps_min":8,"reps_max":12,"rest_seconds":90}]}]
        p1 = await repo.create_plan_tree(user_id=user.id, name="V1", goal="muscle_gain",
                                          duration_weeks=4, weekly_frequency=1, overview="",
                                          days_data=day1)
        await db_session.commit()
        assert p1.version == 1

        p2 = await repo.create_plan_tree(user_id=user.id, name="V2", goal="strength",
                                          duration_weeks=4, weekly_frequency=1, overview="",
                                          days_data=day1)
        await db_session.commit()
        assert p2.version == 2

    @pytest.mark.asyncio
    async def test_activate_archives_others(self, db_session):
        from database.repositories.user_repository import UserRepository
        from database.repositories.exercise_repository import ExerciseRepository
        from database.repositories.training_plan_repository import TrainingPlanRepository

        ur = UserRepository(db_session)
        user = await ur.create(email=f"act_{uuid.uuid4().hex[:8]}@test.com", display_name="Act")
        await db_session.commit()

        er = ExerciseRepository(db_session)
        exs, _ = await er.list_filtered(limit=1)

        repo = TrainingPlanRepository(db_session)
        day = [{"day_index":1,"title":"D1","exercises":[{"exercise_id":str(exs[0].id),"order_index":1,"sets":3,"reps_min":8,"reps_max":12,"rest_seconds":90}]}]
        p1 = await repo.create_plan_tree(user_id=user.id, name="P1", goal="muscle_gain", duration_weeks=4, weekly_frequency=1, overview="", days_data=day)
        p2 = await repo.create_plan_tree(user_id=user.id, name="P2", goal="strength", duration_weeks=4, weekly_frequency=1, overview="", days_data=day)
        await db_session.commit()

        await repo.activate_for_user(p1.id, user.id)
        await db_session.commit()

        await repo.activate_for_user(p2.id, user.id)
        await db_session.commit()

        loaded_p1 = await repo.get_by_id(p1.id)
        loaded_p2 = await repo.get_by_id(p2.id)
        assert str(loaded_p1.status.value) == "archived"
        assert str(loaded_p2.status.value) == "active"

    @pytest.mark.asyncio
    async def test_cannot_access_other_users_plan(self, db_session):
        from database.repositories.user_repository import UserRepository
        from database.repositories.exercise_repository import ExerciseRepository
        from database.repositories.training_plan_repository import TrainingPlanRepository

        ur = UserRepository(db_session)
        u1 = await ur.create(email=f"ou1_{uuid.uuid4().hex[:8]}@test.com", display_name="U1")
        u2 = await ur.create(email=f"ou2_{uuid.uuid4().hex[:8]}@test.com", display_name="U2")
        await db_session.commit()

        er = ExerciseRepository(db_session)
        exs, _ = await er.list_filtered(limit=1)

        repo = TrainingPlanRepository(db_session)
        day = [{"day_index":1,"title":"D1","exercises":[{"exercise_id":str(exs[0].id),"order_index":1,"sets":3,"reps_min":8,"reps_max":12,"rest_seconds":90}]}]
        p1 = await repo.create_plan_tree(user_id=u1.id, name="U1 Plan", goal="muscle_gain", duration_weeks=4, weekly_frequency=1, overview="", days_data=day)
        await db_session.commit()

        result = await repo.get_by_id_for_user(p1.id, u2.id)
        assert result is None


# ── Mocked LLM generation tests ──────────────────────────────────────────────

class TestPlanGenerationWithMockLLM:
    @pytest.mark.asyncio
    async def test_generation_with_mock_llm(self, db_session):
        from services.plan_generation_service import PlanGenerationService, GeneratedPlan
        from database.repositories.exercise_repository import ExerciseRepository

        er = ExerciseRepository(db_session)
        exs, _ = await er.list_filtered(equipment="dumbbell", limit=5)
        assert len(exs) >= 3

        mock_response = GeneratedPlan(
            name="Mock Plan",
            goal="muscle_gain",
            duration_weeks=4,
            weekly_frequency=2,
            overview="Generated by mock",
            days=[
                {
                    "day_index": 1, "title": "Upper",
                    "exercises": [
                        {"exercise_id": str(exs[0].id), "exercise_name": exs[0].name,
                         "order_index": 1, "sets": 3, "reps_min": 8, "reps_max": 12,
                         "rest_seconds": 90, "target_rpe": 7.5},
                        {"exercise_id": str(exs[1].id), "exercise_name": exs[1].name,
                         "order_index": 2, "sets": 3, "reps_min": 10, "reps_max": 15,
                         "rest_seconds": 60, "target_rpe": None},
                    ],
                },
                {
                    "day_index": 2, "title": "Lower",
                    "exercises": [
                        {"exercise_id": str(exs[2].id), "exercise_name": exs[2].name,
                         "order_index": 1, "sets": 4, "reps_min": 8, "reps_max": 10,
                         "rest_seconds": 120, "target_rpe": 8.0},
                    ],
                },
            ],
        )

        from services.plan_validation_service import PlanValidationService

        profile = MagicMock()
        profile.experience_level = "intermediate"
        profile.weekly_frequency = 2
        profile.available_equipment = ["dumbbell"]
        profile.excluded_exercises = []
        profile.target_muscles = []

        svc = PlanValidationService()
        result = svc.validate_plan(mock_response.model_dump(), profile, exs[:5])
        assert result.is_valid, f"Errors: {[str(e) for e in result.errors]}"

    def test_parse_response_handles_markdown_fences(self):
        from services.plan_generation_service import PlanGenerationService
        svc = PlanGenerationService(api_key="fake", base_url="https://fake.api", model="fake")

        raw = '{"name": "Test", "goal": "muscle_gain", "duration_weeks": 4, "weekly_frequency": 1, "overview": "", "days": [{"day_index": 1, "title": "D1", "exercises": [{"exercise_id": "00000000-0000-0000-0000-000000000001", "exercise_name": "Test Ex", "order_index": 1, "sets": 3, "reps_min": 8, "reps_max": 12, "rest_seconds": 90}]}]}'

        # Test plain JSON
        result = svc._parse_response(raw)
        assert result.name == "Test"
        assert len(result.days) == 1

        # Test with markdown fences
        fenced = "```json\n" + raw + "\n```"
        result2 = svc._parse_response(fenced)
        assert result2.name == "Test"


# ── Regression tests ─────────────────────────────────────────────────────────

def test_health_endpoint_works():
    import requests
    r = requests.get("http://localhost:8000/health", timeout=10)
    assert r.status_code == 200


def test_health_database_works():
    import requests
    r = requests.get("http://localhost:8000/health/database", timeout=10)
    assert r.status_code == 200


def test_exercises_endpoint_works():
    import requests
    r = requests.get("http://localhost:8000/exercises?limit=5", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 20


def test_agent_modules_import():
    from agents.agent_orchestrator import AgentOrchestrator, CoachAgent, PlanAgent, ProgressAgent
    from core.intent_recognizer import IntentRecognizer
    assert CoachAgent is not None
    assert PlanAgent is not None
