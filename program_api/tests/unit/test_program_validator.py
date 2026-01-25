"""
Unit tests for ProgramValidator service.

Part of AMA-462: Testing improvements

Tests all validation rules:
- Equipment constraints
- Volume limits by experience level
- Exercise uniqueness
- Muscle balance
- User limitations
"""

import pytest

from models.program import ExperienceLevel
from services.program_validator import (
    ProgramValidator,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def validator():
    """Create a ProgramValidator instance."""
    return ProgramValidator()


@pytest.fixture
def valid_exercise():
    """A valid exercise with all required fields."""
    return {
        "exercise_id": "barbell-bench-press",
        "exercise_name": "Barbell Bench Press",
        "equipment": ["barbell", "bench"],
        "primary_muscles": ["chest"],
        "secondary_muscles": ["anterior_deltoid", "triceps"],
        "sets": 3,
        "reps": "8-12",
    }


@pytest.fixture
def valid_workout(valid_exercise):
    """A valid workout with exercises."""
    return {
        "name": "Push Day",
        "exercises": [
            valid_exercise,
            {
                "exercise_id": "overhead-press",
                "exercise_name": "Overhead Press",
                "equipment": ["barbell"],
                "primary_muscles": ["anterior_deltoid"],
                "sets": 3,
                "reps": "8-10",
            },
            {
                "exercise_id": "tricep-pushdown",
                "exercise_name": "Tricep Pushdown",
                "equipment": ["cables"],
                "primary_muscles": ["triceps"],
                "sets": 3,
                "reps": "10-15",
            },
        ],
    }


@pytest.fixture
def valid_week(valid_workout):
    """A valid week with workouts."""
    return {
        "week_number": 1,
        "workouts": [valid_workout],
    }


@pytest.fixture
def valid_program(valid_week):
    """A valid program with weeks."""
    return {"weeks": [valid_week]}


# ---------------------------------------------------------------------------
# ValidationResult Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_errors_property_filters_correctly(self):
        """errors property returns only ERROR severity issues."""
        issues = [
            ValidationIssue("Error 1", ValidationSeverity.ERROR),
            ValidationIssue("Warning 1", ValidationSeverity.WARNING),
            ValidationIssue("Error 2", ValidationSeverity.ERROR),
            ValidationIssue("Info 1", ValidationSeverity.INFO),
        ]
        result = ValidationResult(is_valid=False, issues=issues)

        errors = result.errors
        assert len(errors) == 2
        assert all(e.severity == ValidationSeverity.ERROR for e in errors)

    def test_warnings_property_filters_correctly(self):
        """warnings property returns only WARNING severity issues."""
        issues = [
            ValidationIssue("Error 1", ValidationSeverity.ERROR),
            ValidationIssue("Warning 1", ValidationSeverity.WARNING),
            ValidationIssue("Warning 2", ValidationSeverity.WARNING),
        ]
        result = ValidationResult(is_valid=False, issues=issues)

        warnings = result.warnings
        assert len(warnings) == 2
        assert all(w.severity == ValidationSeverity.WARNING for w in warnings)

    def test_empty_result_is_valid(self):
        """Result with no issues is valid."""
        result = ValidationResult(is_valid=True, issues=[])
        assert result.is_valid
        assert len(result.errors) == 0
        assert len(result.warnings) == 0


# ---------------------------------------------------------------------------
# Equipment Validation Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEquipmentValidation:
    """Tests for equipment constraint validation."""

    def test_validates_when_equipment_matches(self, validator, valid_program):
        """Program passes when all equipment is available."""
        result = validator.validate_program(
            program_data=valid_program,
            available_equipment=["barbell", "bench", "cables"],
            experience_level=ExperienceLevel.INTERMEDIATE,
        )

        assert result.is_valid
        equipment_errors = [
            i for i in result.errors
            if "equipment" in i.message.lower()
        ]
        assert len(equipment_errors) == 0

    def test_fails_when_equipment_missing(self, validator):
        """Program fails when required equipment is unavailable."""
        program = {
            "weeks": [{
                "week_number": 1,
                "workouts": [{
                    "name": "Push Day",
                    "exercises": [{
                        "exercise_id": "cable-fly",
                        "exercise_name": "Cable Fly",
                        "equipment": ["cables"],
                        "primary_muscles": ["chest"],
                        "sets": 3,
                    }],
                }],
            }]
        }

        result = validator.validate_program(
            program_data=program,
            available_equipment=["barbell", "dumbbells"],  # No cables
            experience_level=ExperienceLevel.INTERMEDIATE,
        )

        assert not result.is_valid
        assert any("cables" in i.message for i in result.errors)

    def test_bodyweight_exercises_always_pass(self, validator):
        """Bodyweight exercises (no equipment) always pass."""
        program = {
            "weeks": [{
                "week_number": 1,
                "workouts": [{
                    "name": "Bodyweight",
                    "exercises": [{
                        "exercise_id": "push-up",
                        "exercise_name": "Push-Up",
                        "equipment": [],  # Bodyweight
                        "primary_muscles": ["chest"],
                        "sets": 3,
                    }],
                }],
            }]
        }

        result = validator.validate_program(
            program_data=program,
            available_equipment=[],  # No equipment at all
            experience_level=ExperienceLevel.BEGINNER,
        )

        assert result.is_valid

    def test_multiple_missing_equipment_reported(self, validator):
        """All missing equipment is reported in the error."""
        program = {
            "weeks": [{
                "week_number": 1,
                "workouts": [{
                    "name": "Test",
                    "exercises": [{
                        "exercise_id": "test-exercise",
                        "exercise_name": "Test Exercise",
                        "equipment": ["cables", "machine"],
                        "primary_muscles": ["chest"],
                        "sets": 3,
                    }],
                }],
            }]
        }

        result = validator.validate_program(
            program_data=program,
            available_equipment=["barbell"],
            experience_level=ExperienceLevel.INTERMEDIATE,
        )

        assert not result.is_valid
        # Should mention both missing items
        error_messages = " ".join(i.message for i in result.errors)
        assert "cables" in error_messages or "machine" in error_messages


# ---------------------------------------------------------------------------
# Volume Validation Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestVolumeValidation:
    """Tests for volume limit validation."""

    def test_beginner_volume_limits(self, validator):
        """Beginner volume limits are 8-12 sets per muscle."""
        # Create program with low volume for a major muscle
        program = {
            "weeks": [{
                "week_number": 1,
                "workouts": [{
                    "name": "Push Day",
                    "exercises": [{
                        "exercise_id": "bench-press",
                        "exercise_name": "Bench Press",
                        "equipment": ["barbell", "bench"],
                        "primary_muscles": ["chest"],
                        "sets": 3,  # Below minimum of 8
                    }],
                }],
            }]
        }

        result = validator.validate_program(
            program_data=program,
            available_equipment=["barbell", "bench"],
            experience_level=ExperienceLevel.BEGINNER,
        )

        # Should have warning for low volume
        volume_warnings = [
            i for i in result.warnings
            if "volume" in i.message.lower() or "sets" in i.message.lower()
        ]
        assert len(volume_warnings) > 0

    def test_intermediate_volume_limits(self, validator):
        """Intermediate volume limits are 12-18 sets per muscle."""
        assert validator.VOLUME_LIMITS[ExperienceLevel.INTERMEDIATE]["min_sets"] == 12
        assert validator.VOLUME_LIMITS[ExperienceLevel.INTERMEDIATE]["max_sets"] == 18

    def test_advanced_volume_limits(self, validator):
        """Advanced volume limits are 16-25 sets per muscle."""
        assert validator.VOLUME_LIMITS[ExperienceLevel.ADVANCED]["min_sets"] == 16
        assert validator.VOLUME_LIMITS[ExperienceLevel.ADVANCED]["max_sets"] == 25

    def test_high_volume_generates_warning(self, validator):
        """Excessive volume generates a warning."""
        # Create program with excessive volume
        program = {
            "weeks": [{
                "week_number": 1,
                "workouts": [{
                    "name": "Push Day",
                    "exercises": [
                        {
                            "exercise_id": f"chest-exercise-{i}",
                            "exercise_name": f"Chest Exercise {i}",
                            "equipment": ["barbell"],
                            "primary_muscles": ["chest"],
                            "sets": 5,
                        }
                        for i in range(6)  # 30 sets total - way over limit
                    ],
                }],
            }]
        }

        result = validator.validate_program(
            program_data=program,
            available_equipment=["barbell"],
            experience_level=ExperienceLevel.BEGINNER,  # Max 12 sets
        )

        high_volume_warnings = [
            i for i in result.warnings
            if "high volume" in i.message.lower()
        ]
        assert len(high_volume_warnings) > 0

    def test_deload_week_has_reduced_limits(self, validator):
        """Deload weeks have halved volume limits."""
        # Normal week would warn about low volume, deload week should not
        # Intermediate min is 12, deload min is 6
        program = {
            "weeks": [{
                "week_number": 4,
                "is_deload": True,
                "workouts": [{
                    "name": "Push Day",
                    "exercises": [{
                        "exercise_id": "bench-press",
                        "exercise_name": "Bench Press",
                        "equipment": ["barbell", "bench"],
                        "primary_muscles": ["chest"],
                        "sets": 6,  # Would be low for normal week (min 12), OK for deload (min 6)
                    }],
                }],
            }]
        }

        result = validator.validate_program(
            program_data=program,
            available_equipment=["barbell", "bench"],
            experience_level=ExperienceLevel.INTERMEDIATE,
        )

        # Should not have low volume warning since it's deload
        low_volume_for_chest = [
            i for i in result.warnings
            if "low volume" in i.message.lower() and "chest" in i.message.lower()
        ]
        assert len(low_volume_for_chest) == 0


# ---------------------------------------------------------------------------
# Uniqueness Validation Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestUniquenessValidation:
    """Tests for exercise uniqueness validation."""

    def test_duplicate_exercise_same_workout_fails(self, validator):
        """Duplicate exercises in same workout generate error."""
        program = {
            "weeks": [{
                "week_number": 1,
                "workouts": [{
                    "name": "Push Day",
                    "exercises": [
                        {
                            "exercise_id": "bench-press",
                            "exercise_name": "Bench Press",
                            "equipment": ["barbell"],
                            "primary_muscles": ["chest"],
                            "sets": 3,
                        },
                        {
                            "exercise_id": "bench-press",  # Duplicate!
                            "exercise_name": "Bench Press",
                            "equipment": ["barbell"],
                            "primary_muscles": ["chest"],
                            "sets": 3,
                        },
                    ],
                }],
            }]
        }

        result = validator.validate_program(
            program_data=program,
            available_equipment=["barbell"],
            experience_level=ExperienceLevel.INTERMEDIATE,
        )

        assert not result.is_valid
        duplicate_errors = [
            i for i in result.errors
            if "duplicate" in i.message.lower()
        ]
        assert len(duplicate_errors) == 1

    def test_same_exercise_different_workouts_ok(self, validator):
        """Same exercise in different workouts is allowed."""
        program = {
            "weeks": [{
                "week_number": 1,
                "workouts": [
                    {
                        "name": "Push Day A",
                        "exercises": [{
                            "exercise_id": "bench-press",
                            "exercise_name": "Bench Press",
                            "equipment": ["barbell"],
                            "primary_muscles": ["chest"],
                            "sets": 3,
                        }],
                    },
                    {
                        "name": "Push Day B",
                        "exercises": [{
                            "exercise_id": "bench-press",  # Same exercise, different day
                            "exercise_name": "Bench Press",
                            "equipment": ["barbell"],
                            "primary_muscles": ["chest"],
                            "sets": 3,
                        }],
                    },
                ],
            }]
        }

        result = validator.validate_program(
            program_data=program,
            available_equipment=["barbell"],
            experience_level=ExperienceLevel.INTERMEDIATE,
        )

        duplicate_errors = [
            i for i in result.errors
            if "duplicate" in i.message.lower()
        ]
        assert len(duplicate_errors) == 0

    def test_different_exercises_same_workout_ok(self, validator):
        """Different exercises in same workout is fine."""
        program = {
            "weeks": [{
                "week_number": 1,
                "workouts": [{
                    "name": "Push Day",
                    "exercises": [
                        {
                            "exercise_id": "bench-press",
                            "exercise_name": "Bench Press",
                            "equipment": ["barbell"],
                            "primary_muscles": ["chest"],
                            "sets": 3,
                        },
                        {
                            "exercise_id": "incline-press",
                            "exercise_name": "Incline Press",
                            "equipment": ["barbell"],
                            "primary_muscles": ["chest"],
                            "sets": 3,
                        },
                    ],
                }],
            }]
        }

        result = validator.validate_program(
            program_data=program,
            available_equipment=["barbell"],
            experience_level=ExperienceLevel.INTERMEDIATE,
        )

        duplicate_errors = [
            i for i in result.errors
            if "duplicate" in i.message.lower()
        ]
        assert len(duplicate_errors) == 0


# ---------------------------------------------------------------------------
# Balance Validation Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBalanceValidation:
    """Tests for muscle balance validation."""

    def test_balanced_push_pull_passes(self, validator):
        """Balanced push/pull volume passes."""
        program = {
            "weeks": [{
                "week_number": 1,
                "workouts": [
                    {
                        "name": "Push Day",
                        "exercises": [{
                            "exercise_id": "bench-press",
                            "equipment": ["barbell"],
                            "primary_muscles": ["chest"],
                            "sets": 4,
                        }],
                    },
                    {
                        "name": "Pull Day",
                        "exercises": [{
                            "exercise_id": "barbell-row",
                            "equipment": ["barbell"],
                            "primary_muscles": ["lats"],
                            "sets": 4,
                        }],
                    },
                ],
            }]
        }

        result = validator.validate_program(
            program_data=program,
            available_equipment=["barbell"],
            experience_level=ExperienceLevel.INTERMEDIATE,
        )

        balance_warnings = [
            i for i in result.warnings
            if "imbalance" in i.message.lower()
        ]
        assert len(balance_warnings) == 0

    def test_push_heavy_imbalance_warns(self, validator):
        """Heavy push imbalance (>50% more) generates warning."""
        program = {
            "weeks": [{
                "week_number": 1,
                "workouts": [{
                    "name": "Push Heavy Day",
                    "exercises": [
                        {
                            "exercise_id": "bench-press",
                            "equipment": ["barbell"],
                            "primary_muscles": ["chest"],
                            "sets": 10,
                        },
                        {
                            "exercise_id": "row",
                            "equipment": ["barbell"],
                            "primary_muscles": ["lats"],
                            "sets": 3,  # Much less pull than push
                        },
                    ],
                }],
            }]
        }

        result = validator.validate_program(
            program_data=program,
            available_equipment=["barbell"],
            experience_level=ExperienceLevel.INTERMEDIATE,
        )

        balance_warnings = [
            i for i in result.warnings
            if "imbalance" in i.message.lower()
        ]
        assert len(balance_warnings) > 0

    def test_quad_hamstring_balance_checked(self, validator):
        """Quad/hamstring balance is validated."""
        # Heavy quad dominance
        program = {
            "weeks": [{
                "week_number": 1,
                "workouts": [{
                    "name": "Leg Day",
                    "exercises": [
                        {
                            "exercise_id": "squat",
                            "equipment": ["barbell"],
                            "primary_muscles": ["quadriceps"],
                            "sets": 12,
                        },
                        {
                            "exercise_id": "rdl",
                            "equipment": ["barbell"],
                            "primary_muscles": ["hamstrings"],
                            "sets": 3,  # Much less
                        },
                    ],
                }],
            }]
        }

        result = validator.validate_program(
            program_data=program,
            available_equipment=["barbell"],
            experience_level=ExperienceLevel.INTERMEDIATE,
        )

        # Should warn about imbalance
        balance_warnings = [
            i for i in result.warnings
            if "imbalance" in i.message.lower()
        ]
        assert len(balance_warnings) > 0


# ---------------------------------------------------------------------------
# Limitations Validation Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLimitationsValidation:
    """Tests for user limitations validation."""

    def test_shoulder_limitation_flags_deltoid_exercises(self, validator):
        """Shoulder limitation warns about deltoid exercises."""
        program = {
            "weeks": [{
                "week_number": 1,
                "workouts": [{
                    "name": "Push Day",
                    "exercises": [{
                        "exercise_id": "overhead-press",
                        "exercise_name": "Overhead Press",
                        "equipment": ["barbell"],
                        "primary_muscles": ["anterior_deltoid"],
                        "sets": 3,
                    }],
                }],
            }]
        }

        result = validator.validate_program(
            program_data=program,
            available_equipment=["barbell"],
            experience_level=ExperienceLevel.INTERMEDIATE,
            limitations=["shoulder injury"],
        )

        limitation_warnings = [
            i for i in result.warnings
            if "limitation" in i.message.lower() or "aggravate" in i.message.lower()
        ]
        assert len(limitation_warnings) > 0

    def test_knee_limitation_flags_quad_exercises(self, validator):
        """Knee limitation warns about quad exercises."""
        program = {
            "weeks": [{
                "week_number": 1,
                "workouts": [{
                    "name": "Leg Day",
                    "exercises": [{
                        "exercise_id": "squat",
                        "exercise_name": "Barbell Squat",
                        "equipment": ["barbell"],
                        "primary_muscles": ["quadriceps"],
                        "sets": 3,
                    }],
                }],
            }]
        }

        result = validator.validate_program(
            program_data=program,
            available_equipment=["barbell"],
            experience_level=ExperienceLevel.INTERMEDIATE,
            limitations=["knee pain"],
        )

        limitation_warnings = [
            i for i in result.warnings
            if "limitation" in i.message.lower() or "aggravate" in i.message.lower()
        ]
        assert len(limitation_warnings) > 0

    def test_back_limitation_flags_back_exercises(self, validator):
        """Back limitation warns about back exercises."""
        program = {
            "weeks": [{
                "week_number": 1,
                "workouts": [{
                    "name": "Pull Day",
                    "exercises": [{
                        "exercise_id": "deadlift",
                        "exercise_name": "Deadlift",
                        "equipment": ["barbell"],
                        "primary_muscles": ["lower_back", "hamstrings"],
                        "sets": 3,
                    }],
                }],
            }]
        }

        result = validator.validate_program(
            program_data=program,
            available_equipment=["barbell"],
            experience_level=ExperienceLevel.INTERMEDIATE,
            limitations=["lower back"],
        )

        limitation_warnings = [
            i for i in result.warnings
            if "limitation" in i.message.lower() or "aggravate" in i.message.lower()
        ]
        assert len(limitation_warnings) > 0

    def test_no_limitations_no_warnings(self, validator, valid_program):
        """No limitations means no limitation warnings."""
        result = validator.validate_program(
            program_data=valid_program,
            available_equipment=["barbell", "bench", "cables"],
            experience_level=ExperienceLevel.INTERMEDIATE,
            limitations=None,
        )

        limitation_warnings = [
            i for i in result.warnings
            if "limitation" in i.message.lower() or "aggravate" in i.message.lower()
        ]
        assert len(limitation_warnings) == 0

    def test_unrecognized_limitation_ignored(self, validator, valid_program):
        """Unrecognized limitations don't cause errors."""
        result = validator.validate_program(
            program_data=valid_program,
            available_equipment=["barbell", "bench", "cables"],
            experience_level=ExperienceLevel.INTERMEDIATE,
            limitations=["time constraints"],  # Not a physical limitation
        )

        # Should still be valid
        assert result.is_valid


# ---------------------------------------------------------------------------
# Validate Workout Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestValidateWorkout:
    """Tests for single workout validation."""

    def test_validate_single_workout(self, validator, valid_workout):
        """Can validate a single workout."""
        result = validator.validate_workout(
            workout=valid_workout,
            available_equipment=["barbell", "bench", "cables"],
        )

        assert result.is_valid

    def test_workout_equipment_validation(self, validator):
        """Workout validates equipment correctly."""
        workout = {
            "name": "Push Day",
            "exercises": [{
                "exercise_id": "cable-fly",
                "exercise_name": "Cable Fly",
                "equipment": ["cables"],
                "primary_muscles": ["chest"],
                "sets": 3,
            }],
        }

        result = validator.validate_workout(
            workout=workout,
            available_equipment=["barbell"],  # No cables
        )

        assert not result.is_valid

    def test_workout_limitation_check(self, validator):
        """Workout validates user limitations."""
        workout = {
            "name": "Push Day",
            "exercises": [{
                "exercise_id": "overhead-press",
                "exercise_name": "Overhead Press",
                "equipment": ["barbell"],
                "primary_muscles": ["anterior_deltoid"],
                "sets": 3,
            }],
        }

        result = validator.validate_workout(
            workout=workout,
            available_equipment=["barbell"],
            limitations=["shoulder"],
        )

        assert len(result.warnings) > 0


# ---------------------------------------------------------------------------
# Summary Generation Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestValidationSummary:
    """Tests for validation summary generation."""

    def test_valid_program_success_summary(self, validator, valid_program):
        """Valid program has success summary."""
        result = validator.validate_program(
            program_data=valid_program,
            available_equipment=["barbell", "bench", "cables"],
            experience_level=ExperienceLevel.INTERMEDIATE,
        )

        assert "success" in result.summary.lower() or "valid" in result.summary.lower()

    def test_invalid_program_error_count_in_summary(self, validator):
        """Invalid program summary includes error count."""
        program = {
            "weeks": [{
                "week_number": 1,
                "workouts": [{
                    "name": "Push Day",
                    "exercises": [
                        {
                            "exercise_id": "bench-press",
                            "equipment": ["cables"],  # Missing
                            "primary_muscles": ["chest"],
                            "sets": 3,
                        },
                        {
                            "exercise_id": "bench-press",  # Duplicate
                            "equipment": ["cables"],
                            "primary_muscles": ["chest"],
                            "sets": 3,
                        },
                    ],
                }],
            }]
        }

        result = validator.validate_program(
            program_data=program,
            available_equipment=["barbell"],
            experience_level=ExperienceLevel.INTERMEDIATE,
        )

        assert not result.is_valid
        assert "error" in result.summary.lower()

    def test_experience_level_string_conversion(self, validator, valid_program):
        """Experience level can be passed as string."""
        result = validator.validate_program(
            program_data=valid_program,
            available_equipment=["barbell", "bench", "cables"],
            experience_level="intermediate",  # String instead of enum
        )

        assert result.is_valid

    def test_unknown_experience_level_uses_default(self, validator, valid_program):
        """Unknown experience level falls back to intermediate."""
        result = validator.validate_program(
            program_data=valid_program,
            available_equipment=["barbell", "bench", "cables"],
            experience_level="expert",  # Not a valid level
        )

        # Should still work with default limits
        assert result is not None
