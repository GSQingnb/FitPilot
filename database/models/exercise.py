"""Exercise model — standard exercise library."""
import enum
from typing import List, Optional

from sqlalchemy import Boolean, Enum, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDMixin


class Equipment(str, enum.Enum):
    BODYWEIGHT = "bodyweight"
    DUMBBELL = "dumbbell"
    BARBELL = "barbell"
    MACHINE = "machine"
    CABLE = "cable"
    KETTLEBELL = "kettlebell"
    RESISTANCE_BAND = "resistance_band"
    OTHER = "other"


class Difficulty(str, enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class Exercise(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "exercises"

    name: Mapped[str] = mapped_column(
        String(200), unique=True, index=True, nullable=False
    )
    name_en: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    primary_muscle: Mapped[str] = mapped_column(
        String(100), index=True, nullable=False
    )
    secondary_muscles: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    equipment: Mapped[Equipment] = mapped_column(
        Enum(Equipment, name="equipment_enum"), index=True, nullable=False
    )
    difficulty: Mapped[Difficulty] = mapped_column(
        Enum(Difficulty, name="difficulty_enum"), index=True, nullable=False
    )
    movement_pattern: Mapped[str] = mapped_column(
        String(100), index=True, nullable=False
    )
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    common_mistakes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    safety_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    planned_exercises: Mapped[list] = relationship(
        "PlannedExercise", back_populates="exercise"
    )
