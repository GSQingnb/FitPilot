"""Training plan model."""
import enum
import uuid
from typing import TYPE_CHECKING, List

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from database.models.user import User
    from database.models.training_day import TrainingDay


class PlanStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class PlanSource(str, enum.Enum):
    MANUAL = "manual"
    AI_GENERATED = "ai_generated"


class TrainingPlan(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "training_plans"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    goal: Mapped[str] = mapped_column(String(100), nullable=False)
    duration_weeks: Mapped[int] = mapped_column(Integer, nullable=False)
    weekly_frequency: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PlanStatus] = mapped_column(
        Enum(PlanStatus, name="plan_status_enum"),
        default=PlanStatus.DRAFT,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    source: Mapped[PlanSource] = mapped_column(
        Enum(PlanSource, name="plan_source_enum"),
        default=PlanSource.MANUAL,
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="training_plans")
    training_days: Mapped[List["TrainingDay"]] = relationship(
        "TrainingDay",
        back_populates="training_plan",
        cascade="all, delete-orphan",
        order_by="TrainingDay.day_index",
    )
