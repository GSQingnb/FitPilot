"""Pydantic request/response schemas for PostgreSQL domain."""
import uuid
from datetime import date, datetime
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


# ── Workouts ─────────────────────────────────────────────────────────────────

class WorkoutStartRequest(BaseModel):
    training_plan_id: uuid.UUID
    training_day_id: uuid.UUID


class WorkoutCompleteRequest(BaseModel):
    notes: Optional[str] = Field(default=None, max_length=2000)
    perceived_difficulty: Optional[float] = Field(default=None, ge=1.0, le=10.0)


class WorkoutCancelRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


class WorkoutSetCreate(BaseModel):
    set_index: int = Field(..., ge=1)
    set_type: str = Field(default="working")
    weight_kg: Optional[float] = Field(default=None, ge=0)
    reps: Optional[int] = Field(default=None, ge=0)
    duration_seconds: Optional[int] = Field(default=None, ge=0)
    distance_meters: Optional[float] = Field(default=None, ge=0)
    rpe: Optional[float] = Field(default=None, ge=1.0, le=10.0)
    is_completed: bool = True
    notes: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_has_data(self):
        if not self.reps and not self.duration_seconds and not self.distance_meters:
            raise ValueError("At least one of reps, duration_seconds, or distance_meters required")
        return self


class WorkoutSetUpdate(BaseModel):
    set_type: Optional[str] = None
    weight_kg: Optional[float] = Field(default=None, ge=0)
    reps: Optional[int] = Field(default=None, ge=0)
    duration_seconds: Optional[int] = Field(default=None, ge=0)
    distance_meters: Optional[float] = Field(default=None, ge=0)
    rpe: Optional[float] = Field(default=None, ge=1.0, le=10.0)
    is_completed: Optional[bool] = None
    notes: Optional[str] = Field(default=None, max_length=500)


class WorkoutSetResponse(BaseModel):
    id: uuid.UUID
    set_index: int
    set_type: str
    weight_kg: Optional[float] = None
    reps: Optional[int] = None
    duration_seconds: Optional[int] = None
    distance_meters: Optional[float] = None
    rpe: Optional[float] = None
    is_completed: bool
    notes: Optional[str] = None


class WorkoutExerciseResponse(BaseModel):
    id: uuid.UUID
    exercise_id: uuid.UUID
    exercise_name: str
    primary_muscle: str
    equipment: str
    status: str
    order_index: int
    planned_sets: Optional[int] = None
    planned_reps_min: Optional[int] = None
    planned_reps_max: Optional[int] = None
    notes: Optional[str] = None
    sets: List[WorkoutSetResponse] = Field(default_factory=list)


class WorkoutStats(BaseModel):
    total_exercises: int
    completed_exercises: int
    skipped_exercises: int
    total_sets: int
    completed_sets: int
    total_reps: int
    total_volume: float


class WorkoutSessionDetailResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    training_plan_id: Optional[uuid.UUID] = None
    training_day_id: Optional[uuid.UUID] = None
    training_day_title: Optional[str] = None
    exercise_count: int
    completed_set_count: int
    notes: Optional[str] = None
    perceived_difficulty: Optional[float] = None
    exercises: List[WorkoutExerciseResponse] = Field(default_factory=list)
    stats: Optional[WorkoutStats] = None


class WorkoutSessionSummaryResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    training_plan_id: Optional[uuid.UUID] = None
    training_day_id: Optional[uuid.UUID] = None
    training_day_title: Optional[str] = None
    exercise_count: int
    completed_set_count: int
    notes: Optional[str] = None
    perceived_difficulty: Optional[float] = None


class WorkoutSessionListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[WorkoutSessionSummaryResponse]


class WorkoutExerciseStatusRequest(BaseModel):
    """Skip exercise reason."""
    reason: Optional[str] = Field(default=None, max_length=500)


# ── Analytics ────────────────────────────────────────────────────────────────

class AnalyticsOverviewResponse(BaseModel):
    period: dict
    completed_workouts: int
    total_duration_seconds: int
    average_duration_seconds: float
    completed_sets: int
    total_reps: int
    total_volume: float
    average_rpe: Optional[float] = None
    current_streak_days: int
    longest_streak_days: int
    data_quality: dict


class WeeklyAnalyticsPoint(BaseModel):
    week_start: str
    completed_workouts: int
    completed_sets: int
    total_reps: int
    total_volume: float
    average_rpe: Optional[float] = None
    total_duration_seconds: int


class ExerciseTrendPoint(BaseModel):
    date: str
    max_weight: Optional[float] = None
    total_volume: float
    total_reps: int
    average_rpe: Optional[float] = None


class ExerciseSummary(BaseModel):
    session_count: int
    completed_set_count: int
    total_reps: int
    total_volume: float
    max_weight: Optional[float] = None
    best_set_reps: Optional[int] = None
    average_rpe: Optional[float] = None
    last_performed_at: Optional[str] = None


class ExerciseTrendResponse(BaseModel):
    exercise: dict
    summary: ExerciseSummary
    trend: List[ExerciseTrendPoint]
    trend_direction: str


class MuscleDistributionItem(BaseModel):
    primary_muscle: str
    completed_sets: int
    total_reps: int
    total_volume: float
    percentage_by_sets: float


# ── Weekly Reports ──────────────────────────────────────────────────────────

class WeeklyReportGenerateRequest(BaseModel):
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    force: bool = False


class WeeklyReportResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    period_start: str
    period_end: str
    status: str
    source: str
    model_name: Optional[str] = None
    metrics: dict
    summary: str
    highlights: list
    issues: list
    recommendations: list
    created_at: str
    updated_at: str


class WeeklyReportListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[WeeklyReportResponse]


# ── Auth ────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str = Field(..., max_length=320)
    display_name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=320)
    password: str = Field(..., max_length=128)


class TokenUser(BaseModel):
    id: str
    email: str
    display_name: str
    is_active: bool


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: TokenUser
