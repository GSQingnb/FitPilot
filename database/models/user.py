"""User model."""
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from database.models.fitness_profile import FitnessProfile
    from database.models.training_plan import TrainingPlan


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(320), unique=True, index=True, nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    fitness_profile: Mapped[Optional["FitnessProfile"]] = relationship(
        "FitnessProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    training_plans: Mapped[List["TrainingPlan"]] = relationship(
        "TrainingPlan",
        back_populates="user",
        cascade="all, delete-orphan",
    )
