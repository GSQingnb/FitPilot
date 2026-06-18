"""FitPilot database integration tests — requires running PostgreSQL.

Run with:
    DATABASE_URL=postgresql+asyncpg://fitpilot:password@localhost:5432/fitpilot pytest tests/test_database.py -q
"""

import os
import sys
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Use test database URL or default to local
TEST_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://fitpilot:0000@localhost:5432/fitpilot",
)


@pytest_asyncio.fixture
async def db_session():
    """Create a fresh async session for each test, rollback after."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()
    await engine.dispose()


# ── 1. Database connectivity ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_database_connectivity(db_session):
    """Verify we can connect and execute a query."""
    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1


@pytest.mark.asyncio
async def test_tables_exist(db_session):
    """Verify all 6 tables exist in the database."""
    expected = {"users", "fitness_profiles", "exercises", "training_plans",
                "training_days", "planned_exercises"}
    result = await db_session.execute(
        text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    )
    tables = {row[0] for row in result.fetchall()}
    missing = expected - tables
    assert not missing, f"Missing tables: {missing}"


# ── 2. User CRUD ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_user(db_session):
    from database.repositories.user_repository import UserRepository

    repo = UserRepository(db_session)
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    user = await repo.create(email=email, display_name="Test")
    await db_session.commit()

    assert user.id is not None
    assert user.email == email
    assert user.is_active is True


@pytest.mark.asyncio
async def test_duplicate_email(db_session):
    from database.repositories.user_repository import UserRepository
    from sqlalchemy.exc import IntegrityError

    repo = UserRepository(db_session)
    email = f"dup_{uuid.uuid4().hex[:8]}@example.com"
    await repo.create(email=email, display_name="First")
    await db_session.commit()

    # Second create should raise IntegrityError
    with pytest.raises(IntegrityError):
        await repo.create(email=email, display_name="Second")
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_get_user_by_id(db_session):
    from database.repositories.user_repository import UserRepository

    repo = UserRepository(db_session)
    email = f"get_{uuid.uuid4().hex[:8]}@example.com"
    user = await repo.create(email=email, display_name="GetMe")
    await db_session.commit()

    fetched = await repo.get_by_id(user.id)
    assert fetched is not None
    assert fetched.email == email

    # Non-existent user
    assert await repo.get_by_id(uuid.uuid4()) is None


@pytest.mark.asyncio
async def test_user_has_timestamps(db_session):
    from database.repositories.user_repository import UserRepository

    repo = UserRepository(db_session)
    user = await repo.create(email=f"ts_{uuid.uuid4().hex[:8]}@example.com", display_name="TS")
    await db_session.commit()

    assert user.created_at is not None
    assert user.updated_at is not None


# ── 3. Fitness Profile CRUD ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_fitness_profile(db_session):
    from database.repositories.user_repository import UserRepository
    from database.repositories.fitness_profile_repository import FitnessProfileRepository

    ur = UserRepository(db_session)
    user = await ur.create(email=f"fp_{uuid.uuid4().hex[:8]}@example.com", display_name="FP")
    await db_session.commit()

    fpr = FitnessProfileRepository(db_session)
    profile = await fpr.upsert(
        user_id=user.id,
        goal="muscle_gain",
        experience_level="beginner",
        weekly_frequency=3,
        session_duration_minutes=60,
        available_equipment=["dumbbell"],
        target_muscles=["chest"],
        excluded_exercises=[],
        limitations=None,
    )
    await db_session.commit()

    assert profile.user_id == user.id
    assert str(profile.goal) == "muscle_gain"
    assert profile.weekly_frequency == 3


@pytest.mark.asyncio
async def test_update_fitness_profile(db_session):
    from database.repositories.user_repository import UserRepository
    from database.repositories.fitness_profile_repository import FitnessProfileRepository

    ur = UserRepository(db_session)
    user = await ur.create(email=f"fp2_{uuid.uuid4().hex[:8]}@example.com", display_name="FP2")
    await db_session.commit()

    fpr = FitnessProfileRepository(db_session)
    # Create
    await fpr.upsert(
        user_id=user.id, goal="fat_loss", experience_level="beginner",
        weekly_frequency=2, session_duration_minutes=45,
        available_equipment=["bodyweight"], target_muscles=[], excluded_exercises=[], limitations=None,
    )
    await db_session.commit()

    # Update
    updated = await fpr.upsert(
        user_id=user.id, goal="strength", experience_level="intermediate",
        weekly_frequency=4, session_duration_minutes=90,
        available_equipment=["barbell"], target_muscles=["full_body"],
        excluded_exercises=["deadlift"], limitations="knee sensitive",
    )
    await db_session.commit()

    assert str(updated.goal) == "strength"
    assert updated.weekly_frequency == 4
    assert "barbell" in updated.available_equipment


@pytest.mark.asyncio
async def test_fitness_profile_not_found_for_nonexistent_user(db_session):
    from database.repositories.fitness_profile_repository import FitnessProfileRepository

    fpr = FitnessProfileRepository(db_session)
    profile = await fpr.get_by_user_id(uuid.uuid4())
    assert profile is None


# ── 4. Exercise queries ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_exercise_count(db_session):
    from database.repositories.exercise_repository import ExerciseRepository

    repo = ExerciseRepository(db_session)
    count = await repo.count()
    assert count >= 20, f"Expected at least 20 exercises, got {count}"


@pytest.mark.asyncio
async def test_exercise_filter_by_equipment(db_session):
    from database.repositories.exercise_repository import ExerciseRepository

    repo = ExerciseRepository(db_session)
    exercises, total = await repo.list_filtered(equipment="dumbbell", limit=10)
    assert total > 0
    for e in exercises:
        assert e.equipment.value == "dumbbell"


@pytest.mark.asyncio
async def test_exercise_search(db_session):
    from database.repositories.exercise_repository import ExerciseRepository

    repo = ExerciseRepository(db_session)
    exercises, total = await repo.list_filtered(search="深蹲", limit=10)
    assert total >= 1
    names = [e.name for e in exercises]
    assert any("深蹲" in n for n in names)


@pytest.mark.asyncio
async def test_exercise_pagination(db_session):
    from database.repositories.exercise_repository import ExerciseRepository

    repo = ExerciseRepository(db_session)
    page1, total = await repo.list_filtered(limit=5, offset=0)
    page2, _ = await repo.list_filtered(limit=5, offset=5)

    assert len(page1) <= 5
    if len(page1) == 5:
        assert len(page2) >= 1
        # No overlap
        ids1 = {e.id for e in page1}
        ids2 = {e.id for e in page2}
        assert ids1.isdisjoint(ids2)


@pytest.mark.asyncio
async def test_get_exercise_by_id(db_session):
    from database.repositories.exercise_repository import ExerciseRepository

    repo = ExerciseRepository(db_session)
    exercises, _ = await repo.list_filtered(limit=1)
    assert len(exercises) > 0

    exercise = await repo.get_by_id(exercises[0].id)
    assert exercise is not None
    assert exercise.name == exercises[0].name


# ── 5. Seed idempotency ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_seed_idempotent(db_session):
    from database.repositories.exercise_repository import ExerciseRepository

    repo = ExerciseRepository(db_session)
    count_before = await repo.count()

    # Run seed (should add 0 since exercises already exist)
    added = await repo.seed_exercises([
        {"name": "杠铃深蹲", "name_en": "Squat", "primary_muscle": "quadriceps",
         "secondary_muscles": [], "equipment": "barbell", "difficulty": "intermediate",
         "movement_pattern": "squat", "instructions": "Test", "common_mistakes": None,
         "safety_notes": None},
    ])
    await db_session.commit()

    assert added == 0, f"Seed should be idempotent, but added {added}"
    count_after = await repo.count()
    assert count_before == count_after


# ── 6. Model relationships ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_user_profile_relationship(db_session):
    from database.repositories.user_repository import UserRepository
    from database.repositories.fitness_profile_repository import FitnessProfileRepository
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload
    from database.models.user import User

    ur = UserRepository(db_session)
    user = await ur.create(email=f"rel_{uuid.uuid4().hex[:8]}@example.com", display_name="Rel")
    await db_session.commit()

    fpr = FitnessProfileRepository(db_session)
    await fpr.upsert(user_id=user.id, goal="general_fitness", experience_level="beginner",
                     weekly_frequency=3, session_duration_minutes=60,
                     available_equipment=[], target_muscles=[], excluded_exercises=[], limitations=None)
    await db_session.commit()

    # Load user with profile
    result = await db_session.execute(
        select(User).where(User.id == user.id).options(joinedload(User.fitness_profile))
    )
    loaded = result.scalar_one()
    assert loaded.fitness_profile is not None
    # When loaded from DB via joinedload, the enum is properly materialized
    goal_val = loaded.fitness_profile.goal
    goal_str = goal_val.value if hasattr(goal_val, 'value') else str(goal_val)
    assert goal_str == "general_fitness"


# ── 7. Model-level imports (no DB needed) ────────────────────────────────────

def test_model_enums_exist():
    from database.models.fitness_profile import FitnessGoal, ExperienceLevel
    from database.models.exercise import Equipment, Difficulty
    from database.models.training_plan import PlanStatus, PlanSource

    assert FitnessGoal.MUSCLE_GAIN.value == "muscle_gain"
    assert ExperienceLevel.BEGINNER.value == "beginner"
    assert Equipment.DUMBBELL.value == "dumbbell"
    assert Difficulty.INTERMEDIATE.value == "intermediate"
    assert PlanStatus.DRAFT.value == "draft"
    assert PlanSource.AI_GENERATED.value == "ai_generated"


def test_all_models_importable():
    from database.models import User, FitnessProfile, Exercise, TrainingPlan, TrainingDay, PlannedExercise
    assert User.__tablename__ == "users"
    assert FitnessProfile.__tablename__ == "fitness_profiles"
    assert Exercise.__tablename__ == "exercises"
    assert TrainingPlan.__tablename__ == "training_plans"
    assert TrainingDay.__tablename__ == "training_days"
    assert PlannedExercise.__tablename__ == "planned_exercises"


def test_base_mixins():
    from database.base import Base, TimestampMixin, UUIDMixin
    assert hasattr(TimestampMixin, "created_at")
    assert hasattr(TimestampMixin, "updated_at")
    assert hasattr(UUIDMixin, "id")
