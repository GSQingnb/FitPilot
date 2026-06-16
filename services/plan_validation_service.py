"""Business rule validation for generated training plans.

Validates structured plans against user fitness profiles,
exercise availability, and training safety rules before saving.
"""
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

from database.models.exercise import Exercise
from database.models.fitness_profile import FitnessProfile


@dataclass
class ValidationError:
    field: str
    message: str


@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_error(self, field: str, message: str):
        self.errors.append(ValidationError(field=field, message=message))
        self.is_valid = False


class PlanValidationService:
    """Validates generated training plans against business rules."""

    MAX_EXERCISES_PER_DAY = 10
    MAX_EXERCISES_BEGINNER = 6
    MIN_SETS = 1
    MAX_SETS = 10
    MIN_REPS = 1
    MAX_REPS = 100
    MIN_REST = 0
    MAX_REST = 600
    MIN_RPE = 1.0
    MAX_RPE = 10.0
    MIN_DURATION_WEEKS = 1
    MAX_DURATION_WEEKS = 12

    def validate_plan(
        self,
        plan_data: dict,
        profile: FitnessProfile,
        candidate_exercises: List[Exercise],
    ) -> ValidationResult:
        """Validate a generated plan against all business rules."""
        result = ValidationResult(is_valid=True)

        exercise_map = {str(e.id): e for e in candidate_exercises}
        excluded = set(profile.excluded_exercises or [])
        equipment = set(profile.available_equipment or [])

        # ── Plan-level checks ──────────────────────────────────────────────
        name = plan_data.get("name", "")
        if not name or not name.strip():
            result.add_error("plan.name", "Plan name is required")

        dw = plan_data.get("duration_weeks", 0)
        if not isinstance(dw, int) or dw < self.MIN_DURATION_WEEKS or dw > self.MAX_DURATION_WEEKS:
            result.add_error("plan.duration_weeks",
                             f"duration_weeks must be {self.MIN_DURATION_WEEKS}-{self.MAX_DURATION_WEEKS}")

        wf = plan_data.get("weekly_frequency", 0)
        if not isinstance(wf, int) or wf < 1 or wf > 7:
            result.add_error("plan.weekly_frequency", "weekly_frequency must be 1-7")
        if wf != profile.weekly_frequency:
            result.add_error("plan.weekly_frequency",
                             f"weekly_frequency ({wf}) must match profile ({profile.weekly_frequency})")

        days = plan_data.get("days", [])
        if not isinstance(days, list) or len(days) == 0:
            result.add_error("plan.days", "Plan must have at least one training day")
            return result  # can't validate further without days

        if dw and wf and len(days) != wf:
            result.add_error("plan.days", f"Number of days ({len(days)}) must equal weekly_frequency ({wf})")

        seen_day_indices = set()
        for i, day in enumerate(days):
            if not isinstance(day, dict):
                result.add_error(f"days[{i}]", "Each day must be a dict")
                continue

            di = day.get("day_index", 0)
            if not isinstance(di, int) or di < 1:
                result.add_error(f"days[{i}].day_index", "day_index must be >= 1")
            if di in seen_day_indices:
                result.add_error(f"days[{i}].day_index", f"Duplicate day_index: {di}")
            seen_day_indices.add(di)

            if not isinstance(day.get("title", ""), str) or not day["title"].strip():
                result.add_error(f"days[{i}].title", "Each day must have a title")

            exercises = day.get("exercises", [])
            if not isinstance(exercises, list):
                result.add_error(f"days[{i}].exercises", "exercises must be a list")
                continue

            if len(exercises) == 0:
                result.add_error(f"days[{i}].exercises", "Each day must have at least 1 exercise")
            if len(exercises) > self.MAX_EXERCISES_PER_DAY:
                result.add_error(f"days[{i}].exercises",
                                 f"Max {self.MAX_EXERCISES_PER_DAY} exercises per day")

            # Beginner-specific: fewer exercises
            if profile.experience_level and str(profile.experience_level) == "beginner":
                if len(exercises) > self.MAX_EXERCISES_BEGINNER:
                    result.add_error(f"days[{i}].exercises",
                                     f"Beginner max {self.MAX_EXERCISES_BEGINNER} exercises per day")

            seen_order = set()
            seen_exercise_ids = set()
            for j, ex in enumerate(exercises):
                if not isinstance(ex, dict):
                    result.add_error(f"days[{i}].exercises[{j}]", "Must be a dict")
                    continue

                eid = ex.get("exercise_id", "")
                ename = ex.get("exercise_name", "?")
                label = f"days[{i}].exercises[{j}] ({ename})"

                # Exercise must exist in candidate list
                if not eid or str(eid) not in exercise_map:
                    result.add_error(label, f"exercise_id '{eid}' not in candidate exercises")
                else:
                    db_ex = exercise_map[str(eid)]
                    # Soft check: must be active
                    if not db_ex.is_active:
                        result.add_error(label, f"Exercise '{db_ex.name}' is not active")
                    # Must not be excluded
                    if db_ex.name in excluded or str(db_ex.id) in excluded:
                        result.add_error(label, f"Exercise '{db_ex.name}' is in user's excluded list")
                    # Equipment must be available
                    if db_ex.equipment and str(db_ex.equipment.value) not in equipment:
                        result.add_error(label,
                                         f"Equipment '{db_ex.equipment.value}' not in user's available equipment ({equipment})")

                # Duplicate exercise in same day
                if eid in seen_exercise_ids:
                    result.add_error(label, f"Duplicate exercise in same day")
                if eid:
                    seen_exercise_ids.add(eid)

                # order_index checks
                oi = ex.get("order_index", 0)
                if not isinstance(oi, int):
                    result.add_error(label, "order_index must be int")
                elif oi in seen_order:
                    result.add_error(label, f"Duplicate order_index: {oi}")
                seen_order.add(oi)

                # Sets, reps, rest
                sets = ex.get("sets", 0)
                if not isinstance(sets, int) or sets < self.MIN_SETS or sets > self.MAX_SETS:
                    result.add_error(label, f"sets must be {self.MIN_SETS}-{self.MAX_SETS}, got {sets}")

                rmin = ex.get("reps_min", 0)
                rmax = ex.get("reps_max", 0)
                if not isinstance(rmin, int) or rmin < self.MIN_REPS or rmin > self.MAX_REPS:
                    result.add_error(label, f"reps_min must be {self.MIN_REPS}-{self.MAX_REPS}")
                if not isinstance(rmax, int) or rmax < self.MIN_REPS or rmax > self.MAX_REPS:
                    result.add_error(label, f"reps_max must be {self.MIN_REPS}-{self.MAX_REPS}")
                if rmin > rmax:
                    result.add_error(label, f"reps_min ({rmin}) > reps_max ({rmax})")

                rest = ex.get("rest_seconds", 0)
                if not isinstance(rest, int) or rest < self.MIN_REST or rest > self.MAX_REST:
                    result.add_error(label, f"rest_seconds must be {self.MIN_REST}-{self.MAX_REST}")

                rpe = ex.get("target_rpe")
                if rpe is not None:
                    if not isinstance(rpe, (int, float)):
                        result.add_error(label, "target_rpe must be float or null")
                    elif rpe < self.MIN_RPE or rpe > self.MAX_RPE:
                        result.add_error(label, f"target_rpe must be {self.MIN_RPE}-{self.MAX_RPE}")

        return result
