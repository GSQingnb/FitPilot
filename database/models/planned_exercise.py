"""Planned exercise model — exercise within a training day."""
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from database.models.training_day import TrainingDay
    from database.models.exercise import Exercise


class PlannedExercise(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "planned_exercises"
    __table_args__ = (
        UniqueConstraint("training_day_id", "order_index", name="uq_training_day_order"),
    )

    training_day_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("training_days.id", ondelete="CASCADE"),
        nullable=False,
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exercises.id", ondelete="RESTRICT"),
        nullable=False,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    sets: Mapped[int] = mapped_column(Integer, nullable=False)
    reps_min: Mapped[int] = mapped_column(Integer, nullable=False)
    reps_max: Mapped[int] = mapped_column(Integer, nullable=False)
    rest_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    target_rpe: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    training_day: Mapped["TrainingDay"] = relationship(
        "TrainingDay", back_populates="planned_exercises"
    )
    exercise: Mapped["Exercise"] = relationship(
        "Exercise", back_populates="planned_exercises"
    )
