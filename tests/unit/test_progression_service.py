"""
Unit tests for Progression Service.

Part of AMA-299: Exercise Progression Tracking
Phase 3 - Progression Features

Tests cover:
- 1RM calculation formulas (Brzycki and Epley)
- Progression service business logic
"""
import pytest
from datetime import date, timedelta

from backend.core.progression_service import (
    calculate_1rm,
    calculate_1rm_brzycki,
    calculate_1rm_epley,
    ProgressionService,
    ExerciseHistoryResponse,
    PersonalRecordResponse,
    LastWeightResponse,
)
from tests.fakes import FakeProgressionRepository, FakeExercisesRepository


# =============================================================================
# 1RM Formula Tests
# =============================================================================


@pytest.mark.unit
class TestBrzyckiFormula:
    """Tests for the Brzycki 1RM formula."""

    def test_single_rep_returns_weight(self):
        """1 rep means the weight IS the 1RM."""
        assert calculate_1rm_brzycki(225, 1) == 225.0

    def test_zero_reps_returns_zero(self):
        """0 reps should return 0."""
        assert calculate_1rm_brzycki(225, 0) == 0.0

    def test_standard_5_reps(self):
        """Test standard 5-rep calculation."""
        # 185 lbs x 5 reps ≈ 208 lbs 1RM
        result = calculate_1rm_brzycki(185, 5)
        assert 207 < result < 210

    def test_8_rep_calculation(self):
        """Test 8-rep calculation."""
        # 135 lbs x 8 reps ≈ 168 lbs 1RM
        result = calculate_1rm_brzycki(135, 8)
        assert 167 < result < 170

    def test_10_rep_calculation(self):
        """Test 10-rep calculation (edge of accuracy)."""
        # 100 lbs x 10 reps ≈ 133 lbs 1RM
        result = calculate_1rm_brzycki(100, 10)
        assert 132 < result < 135

    def test_high_reps_capped(self):
        """Test that extremely high reps don't break the formula."""
        # Formula would divide by zero at 37 reps
        result = calculate_1rm_brzycki(50, 37)
        assert result > 0  # Should return a reasonable value


@pytest.mark.unit
class TestEpleyFormula:
    """Tests for the Epley 1RM formula."""

    def test_single_rep_returns_weight(self):
        """1 rep means the weight IS the 1RM."""
        assert calculate_1rm_epley(225, 1) == 225.0

    def test_zero_reps_returns_zero(self):
        """0 reps should return 0."""
        assert calculate_1rm_epley(225, 0) == 0.0

    def test_standard_5_reps(self):
        """Test standard 5-rep calculation."""
        # 185 lbs x 5 reps = 185 * (1 + 5/30) = 185 * 1.167 ≈ 216
        result = calculate_1rm_epley(185, 5)
        assert 215 < result < 217

    def test_10_rep_calculation(self):
        """Test 10-rep calculation."""
        # 100 lbs x 10 reps = 100 * (1 + 10/30) = 100 * 1.333 ≈ 133
        result = calculate_1rm_epley(100, 10)
        assert 132 < result < 135

    def test_20_rep_calculation(self):
        """Test higher rep calculation (where Epley works better)."""
        # 50 lbs x 20 reps = 50 * (1 + 20/30) = 50 * 1.667 ≈ 83
        result = calculate_1rm_epley(50, 20)
        assert 82 < result < 84


@pytest.mark.unit
class TestCalculate1RM:
    """Tests for the unified calculate_1rm function."""

    def test_default_formula_is_brzycki(self):
        """Default should use Brzycki formula."""
        brzycki_result = calculate_1rm_brzycki(185, 5)
        default_result = calculate_1rm(185, 5)
        assert default_result == round(brzycki_result, 1)

    def test_explicit_brzycki(self):
        """Can explicitly specify Brzycki."""
        result = calculate_1rm(185, 5, "brzycki")
        assert result == round(calculate_1rm_brzycki(185, 5), 1)

    def test_explicit_epley(self):
        """Can explicitly specify Epley."""
        result = calculate_1rm(185, 5, "epley")
        assert result == round(calculate_1rm_epley(185, 5), 1)

    def test_result_is_rounded(self):
        """Result should be rounded to 1 decimal place."""
        result = calculate_1rm(185, 5, "brzycki")
        # Check it has at most 1 decimal place
        assert result == round(result, 1)


# =============================================================================
# Progression Service Tests
# =============================================================================


@pytest.fixture
def exercises_repo():
    """Create a fake exercises repository with test data."""
    return FakeExercisesRepository(exercises=[
        {
            "id": "barbell-bench-press",
            "name": "Barbell Bench Press",
            "aliases": ["Bench Press", "Flat Bench"],
            "primary_muscles": ["chest"],
            "secondary_muscles": ["triceps", "shoulders"],
            "equipment": ["barbell", "bench"],
            "supports_1rm": True,
            "one_rm_formula": "brzycki",
            "category": "compound",
        },
        {
            "id": "barbell-squat",
            "name": "Barbell Squat",
            "aliases": ["Back Squat"],
            "primary_muscles": ["quadriceps"],
            "secondary_muscles": ["glutes", "hamstrings"],
            "equipment": ["barbell", "squat_rack"],
            "supports_1rm": True,
            "one_rm_formula": "brzycki",
            "category": "compound",
        },
        {
            "id": "lateral-raise",
            "name": "Lateral Raise",
            "aliases": ["Side Raise"],
            "primary_muscles": ["shoulders"],
            "equipment": ["dumbbell"],
            "supports_1rm": False,  # Isolation exercises don't support 1RM
            "category": "isolation",
        },
    ])


@pytest.fixture
def progression_repo():
    """Create a fake progression repository with test data."""
    repo = FakeProgressionRepository()

    # Add sessions for bench press
    repo.seed_sessions("test_user", [
        {
            "completion_id": "comp_1",
            "workout_date": "2024-01-15",
            "workout_name": "Push Day",
            "exercise_id": "barbell-bench-press",
            "exercise_name": "Barbell Bench Press",
            "sets": [
                {"set_number": 1, "weight": 185, "weight_unit": "lbs", "reps_completed": 8, "status": "completed"},
                {"set_number": 2, "weight": 185, "weight_unit": "lbs", "reps_completed": 7, "status": "completed"},
                {"set_number": 3, "weight": 185, "weight_unit": "lbs", "reps_completed": 6, "status": "completed"},
            ],
        },
        {
            "completion_id": "comp_2",
            "workout_date": "2024-01-08",
            "workout_name": "Push Day",
            "exercise_id": "barbell-bench-press",
            "exercise_name": "Barbell Bench Press",
            "sets": [
                {"set_number": 1, "weight": 175, "weight_unit": "lbs", "reps_completed": 8, "status": "completed"},
                {"set_number": 2, "weight": 175, "weight_unit": "lbs", "reps_completed": 8, "status": "completed"},
                {"set_number": 3, "weight": 175, "weight_unit": "lbs", "reps_completed": 7, "status": "completed"},
            ],
        },
    ])

    # Add sessions for squat
    repo.seed_sessions("test_user", [
        {
            "completion_id": "comp_3",
            "workout_date": "2024-01-16",
            "workout_name": "Leg Day",
            "exercise_id": "barbell-squat",
            "exercise_name": "Barbell Squat",
            "sets": [
                {"set_number": 1, "weight": 225, "weight_unit": "lbs", "reps_completed": 5, "status": "completed"},
                {"set_number": 2, "weight": 225, "weight_unit": "lbs", "reps_completed": 5, "status": "completed"},
                {"set_number": 3, "weight": 225, "weight_unit": "lbs", "reps_completed": 4, "status": "completed"},
            ],
        },
    ])

    # Add metadata for exercises
    repo.seed_exercise_metadata("barbell-bench-press", {
        "id": "barbell-bench-press",
        "name": "Barbell Bench Press",
        "primary_muscles": ["chest"],
    })
    repo.seed_exercise_metadata("barbell-squat", {
        "id": "barbell-squat",
        "name": "Barbell Squat",
        "primary_muscles": ["quadriceps"],
    })

    return repo


@pytest.fixture
def progression_service(progression_repo, exercises_repo):
    """Create a progression service with test dependencies."""
    return ProgressionService(
        progression_repo=progression_repo,
        exercises_repo=exercises_repo,
    )


@pytest.mark.unit
class TestProgressionServiceHistory:
    """Tests for get_exercise_history."""

    def test_returns_sessions_for_exercise(self, progression_service):
        """Returns sessions for the requested exercise."""
        result = progression_service.get_exercise_history("test_user", "barbell-bench-press")

        assert result is not None
        assert result.exercise_id == "barbell-bench-press"
        assert len(result.sessions) == 2

    def test_includes_1rm_calculations(self, progression_service):
        """Sessions include estimated 1RM for each set."""
        result = progression_service.get_exercise_history("test_user", "barbell-bench-press")

        assert result.supports_1rm is True
        # First set: 185 lbs x 8 reps ≈ 230 lbs 1RM
        first_set = result.sessions[0].sets[0]
        assert first_set.estimated_1rm is not None
        assert 228 < first_set.estimated_1rm < 232

    def test_calculates_session_best_1rm(self, progression_service):
        """Each session has a best 1RM."""
        result = progression_service.get_exercise_history("test_user", "barbell-bench-press")

        # First session best should be from first set (8 reps)
        assert result.sessions[0].session_best_1rm is not None
        assert result.sessions[0].session_best_1rm > 200

    def test_calculates_all_time_best(self, progression_service):
        """Returns all-time best 1RM across sessions."""
        result = progression_service.get_exercise_history("test_user", "barbell-bench-press")

        assert result.all_time_best_1rm is not None
        # Should be from the most recent session at 185 lbs
        assert result.all_time_best_1rm > 220

    def test_returns_none_for_unknown_exercise(self, progression_service):
        """Returns None if exercise doesn't exist."""
        result = progression_service.get_exercise_history("test_user", "unknown-exercise")
        assert result is None

    def test_respects_pagination(self, progression_service):
        """Limit and offset work correctly."""
        result = progression_service.get_exercise_history(
            "test_user",
            "barbell-bench-press",
            limit=1,
            offset=0,
        )

        assert len(result.sessions) == 1
        assert result.total_sessions == 2  # Total is still 2


@pytest.mark.unit
class TestProgressionServiceLastWeight:
    """Tests for get_last_weight."""

    def test_returns_most_recent_weight(self, progression_service):
        """Returns the most recent weight used."""
        result = progression_service.get_last_weight("test_user", "barbell-bench-press")

        assert result is not None
        assert result.weight == 185
        assert result.exercise_id == "barbell-bench-press"

    def test_returns_none_for_no_history(self, progression_service, progression_repo):
        """Returns None if user has no history for exercise."""
        # Clear the repo
        progression_repo.reset()

        result = progression_service.get_last_weight("test_user", "barbell-bench-press")
        assert result is None

    def test_returns_none_for_unknown_exercise(self, progression_service):
        """Returns None if exercise doesn't exist."""
        result = progression_service.get_last_weight("test_user", "unknown-exercise")
        assert result is None


@pytest.mark.unit
class TestProgressionServiceRecords:
    """Tests for get_personal_records."""

    def test_returns_1rm_records(self, progression_service):
        """Returns 1RM records for exercises."""
        result = progression_service.get_personal_records("test_user", record_type="1rm")

        assert len(result.records) > 0
        # Should have records for bench and squat
        exercise_ids = [r["exercise_id"] for r in result.records]
        assert "barbell-bench-press" in exercise_ids

    def test_filters_by_record_type(self, progression_service):
        """Can filter to specific record type."""
        result = progression_service.get_personal_records("test_user", record_type="max_weight")

        for record in result.records:
            assert record["record_type"] == "max_weight"

    def test_filters_by_exercise(self, progression_service):
        """Can filter to specific exercise."""
        result = progression_service.get_personal_records(
            "test_user",
            exercise_id="barbell-bench-press",
        )

        for record in result.records:
            assert record["exercise_id"] == "barbell-bench-press"

    def test_includes_record_details(self, progression_service):
        """1RM records include weight/reps details."""
        result = progression_service.get_personal_records("test_user", record_type="1rm")

        for record in result.records:
            if record["record_type"] == "1rm":
                assert "details" in record
                assert "weight" in record["details"]
                assert "reps" in record["details"]


@pytest.mark.unit
class TestProgressionServiceVolume:
    """Tests for get_volume_analytics."""

    def test_returns_volume_data(self, progression_service):
        """Returns volume data by muscle group."""
        result = progression_service.get_volume_analytics("test_user")

        assert result.data is not None
        assert result.summary is not None
        assert result.granularity == "daily"

    def test_respects_date_range(self, progression_service):
        """Filters by date range."""
        # Request a range that excludes some sessions
        result = progression_service.get_volume_analytics(
            "test_user",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 10),
        )

        # Should only include the Jan 8 session
        assert result.period["start_date"] == "2024-01-01"
        assert result.period["end_date"] == "2024-01-10"

    def test_respects_granularity(self, progression_service):
        """Changes granularity of aggregation."""
        result = progression_service.get_volume_analytics(
            "test_user",
            granularity="weekly",
        )

        assert result.granularity == "weekly"


@pytest.mark.unit
class TestExerciseNooneRM:
    """Tests for exercises that don't support 1RM."""

    def test_no_1rm_for_isolation_exercises(self, progression_service, progression_repo):
        """Isolation exercises don't get 1RM calculations."""
        # Add a session for lateral raise
        progression_repo.seed_sessions("test_user", [
            {
                "completion_id": "comp_4",
                "workout_date": "2024-01-17",
                "workout_name": "Shoulder Day",
                "exercise_id": "lateral-raise",
                "exercise_name": "Lateral Raise",
                "sets": [
                    {"set_number": 1, "weight": 20, "weight_unit": "lbs", "reps_completed": 15, "status": "completed"},
                ],
            },
        ])
        progression_repo.seed_exercise_metadata("lateral-raise", {
            "id": "lateral-raise",
            "name": "Lateral Raise",
            "primary_muscles": ["shoulders"],
        })

        result = progression_service.get_exercise_history("test_user", "lateral-raise")

        assert result is not None
        assert result.supports_1rm is False
        # Sets should not have estimated 1RM
        assert result.sessions[0].sets[0].estimated_1rm is None
