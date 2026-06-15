"""Training day model."""
import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from database.models.training_plan import TrainingPlan
    from database.models.planned_exercise import PlannedExercise


class TrainingDay(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "training_days"
    __table_args__ = (
        UniqueConstraint("training_plan_id", "day_index", name="uq_training_plan_day"),
    )

    training_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("training_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    day_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    training_plan: Mapped["TrainingPlan"] = relationship(
        "TrainingPlan", back_populates="training_days"
    )
    planned_exercises: Mapped[List["PlannedExercise"]] = relationship(
        "PlannedExercise",
        back_populates="training_day",
        cascade="all, delete-orphan",
        order_by="PlannedExercise.order_index",
    )
