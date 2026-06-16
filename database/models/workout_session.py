"""Workout session model — represents a single training session."""
import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from database.models.user import User
    from database.models.training_plan import TrainingPlan
    from database.models.training_day import TrainingDay
    from database.models.workout_exercise import WorkoutExercise


class WorkoutStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class WorkoutSession(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workout_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    training_plan_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("training_plans.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    training_day_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("training_days.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    status: Mapped[WorkoutStatus] = mapped_column(
        Enum(WorkoutStatus, name="workout_status_enum"),
        default=WorkoutStatus.IN_PROGRESS,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    perceived_difficulty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Indexes
    __table_args__ = (
        # Index on status for filtering
    )

    # Relationships
    user: Mapped["User"] = relationship("User")
    training_plan: Mapped[Optional["TrainingPlan"]] = relationship("TrainingPlan")
    training_day: Mapped[Optional["TrainingDay"]] = relationship("TrainingDay")
    workout_exercises: Mapped[List["WorkoutExercise"]] = relationship(
        "WorkoutExercise",
        back_populates="workout_session",
        cascade="all, delete-orphan",
        order_by="WorkoutExercise.order_index",
    )
