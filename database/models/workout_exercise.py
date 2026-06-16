"""Workout exercise model — an actual exercise performed in a session."""
import enum
import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Enum, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from database.models.workout_session import WorkoutSession
    from database.models.planned_exercise import PlannedExercise
    from database.models.exercise import Exercise
    from database.models.workout_set import WorkoutSet


class ExerciseStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class WorkoutExercise(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workout_exercises"
    __table_args__ = (
        UniqueConstraint("workout_session_id", "order_index", name="uq_workout_session_order"),
    )

    workout_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workout_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    planned_exercise_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("planned_exercises.id", ondelete="SET NULL"),
        nullable=True,
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exercises.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ExerciseStatus] = mapped_column(
        Enum(ExerciseStatus, name="exercise_status_enum"),
        default=ExerciseStatus.PENDING,
        nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    workout_session: Mapped["WorkoutSession"] = relationship(
        "WorkoutSession", back_populates="workout_exercises"
    )
    planned_exercise: Mapped[Optional["PlannedExercise"]] = relationship("PlannedExercise")
    exercise: Mapped["Exercise"] = relationship("Exercise")
    workout_sets: Mapped[List["WorkoutSet"]] = relationship(
        "WorkoutSet",
        back_populates="workout_exercise",
        cascade="all, delete-orphan",
        order_by="WorkoutSet.set_index",
    )
