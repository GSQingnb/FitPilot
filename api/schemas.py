"""Pydantic request/response schemas for PostgreSQL domain."""
import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


# ── User ──────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: str = Field(..., max_length=320, pattern=r"^[^@]+@[^@]+\.[^@]+$")
    display_name: str = Field(..., min_length=1, max_length=100)


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Fitness Profile ───────────────────────────────────────────────────────────

VALID_GOALS = {"muscle_gain", "fat_loss", "strength", "general_fitness"}
VALID_EXPERIENCE = {"beginner", "intermediate", "advanced"}


class FitnessProfileUpsert(BaseModel):
    goal: str
    experience_level: str
    weekly_frequency: int = Field(..., ge=1, le=7)
    session_duration_minutes: int = Field(..., ge=15, le=240)
    available_equipment: List[str] = Field(default_factory=list)
    target_muscles: List[str] = Field(default_factory=list)
    excluded_exercises: List[str] = Field(default_factory=list)
    limitations: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_enums(self):
        if self.goal not in VALID_GOALS:
            raise ValueError(f"goal must be one of {VALID_GOALS}")
        if self.experience_level not in VALID_EXPERIENCE:
            raise ValueError(f"experience_level must be one of {VALID_EXPERIENCE}")
        return self


class FitnessProfileResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    goal: str
    experience_level: str
    weekly_frequency: int
    session_duration_minutes: int
    available_equipment: list
    target_muscles: list
    excluded_exercises: list
    limitations: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Exercise ──────────────────────────────────────────────────────────────────

class ExerciseResponse(BaseModel):
    id: uuid.UUID
    name: str
    name_en: Optional[str] = None
    primary_muscle: str
    secondary_muscles: list
    equipment: str
    difficulty: str
    movement_pattern: str
    instructions: str
    common_mistakes: Optional[str] = None
    safety_notes: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExerciseListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    exercises: List[ExerciseResponse]


# ── Training Plans ───────────────────────────────────────────────────────────

class TrainingPlanGenerateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    duration_weeks: int = Field(default=4, ge=1, le=12)
    additional_preferences: Optional[str] = Field(default=None, max_length=1000)


class PlannedExerciseInResponse(BaseModel):
    id: uuid.UUID
    exercise_id: uuid.UUID
    exercise_name: str
    primary_muscle: str
    equipment: str
    order_index: int
    sets: int
    reps_min: int
    reps_max: int
    rest_seconds: int
    target_rpe: Optional[float] = None
    notes: Optional[str] = None


class TrainingDayResponse(BaseModel):
    id: uuid.UUID
    day_index: int
    title: str
    notes: Optional[str] = None
    exercises: List[PlannedExerciseInResponse] = Field(default_factory=list)


class TrainingPlanDetailResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    goal: str
    duration_weeks: int
    weekly_frequency: int
    status: str
    source: str
    version: int
    created_at: datetime
    updated_at: datetime
    days: List[TrainingDayResponse] = Field(default_factory=list)


class TrainingPlanSummaryResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    goal: str
    duration_weeks: int
    weekly_frequency: int
    status: str
    source: str
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TrainingPlanListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[TrainingPlanSummaryResponse]
