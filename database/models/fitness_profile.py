"""Fitness profile model."""
import enum
import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from database.models.user import User


class FitnessGoal(str, enum.Enum):
    MUSCLE_GAIN = "muscle_gain"
    FAT_LOSS = "fat_loss"
    STRENGTH = "strength"
    GENERAL_FITNESS = "general_fitness"


class ExperienceLevel(str, enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class FitnessProfile(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "fitness_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    goal: Mapped[FitnessGoal] = mapped_column(
        Enum(FitnessGoal, name="fitness_goal_enum"), nullable=False
    )
    experience_level: Mapped[ExperienceLevel] = mapped_column(
        Enum(ExperienceLevel, name="experience_level_enum"), nullable=False
    )
    weekly_frequency: Mapped[int] = mapped_column(Integer, nullable=False)
    session_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    available_equipment: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    target_muscles: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    excluded_exercises: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    limitations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="fitness_profile")
