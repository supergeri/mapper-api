"""
Unit tests for ExerciseSelector service.

Part of AMA-472: Exercise Database Integration for Program Generation

Tests all ExerciseSelector functionality:
- fill_exercise_slot with various requirements
- Equipment constraint handling
- Exclusion of already-selected exercises
- Alternative exercise lookup
- Fallback exercise creation
- Equipment normalization
"""

import pytest

from services.exercise_selector import (
    EQUIPMENT_MAPPING,
    ExerciseCandidate,
    ExerciseSelector,
    SlotRequirements,
)
from tests.fakes import FakeExerciseRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def exercise_repo():
    """Create a fake exercise repository with default exercises."""
    repo = FakeExerciseRepository()
    repo.seed_default_exercises()
    return repo


@pytest.fixture
def selector(exercise_repo):
    """Create an ExerciseSelector with fake repository."""
    return ExerciseSelector(exercise_repo)


@pytest.fixture
def full_gym_equipment():
    """Full gym equipment list."""
    return ["barbell", "dumbbells", "cables", "bench", "squat_rack", "pull_up_bar"]


@pytest.fixture
def bodyweight_equipment():
    """Bodyweight-only equipment."""
    return ["pull_up_bar"]


# ---------------------------------------------------------------------------
# SlotRequirements Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSlotRequirements:
    """Tests for SlotRequirements dataclass."""

    def test_creates_with_defaults(self):
        """SlotRequirements can be created with all defaults."""
        requirements = SlotRequirements()

        assert requirements.movement_pattern is None
        assert requirements.target_muscles is None
        assert requirements.category is None
        assert requirements.supports_1rm is None
        assert requirements.preferred_equipment is None

    def test_creates_with_all_fields(self):
        """SlotRequirements can be created with all fields."""
        requirements = SlotRequirements(
            movement_pattern="push",
            target_muscles=["chest", "triceps"],
            category="compound",
            supports_1rm=True,
            preferred_equipment=["barbell"],
        )

        assert requirements.movement_pattern == "push"
        assert requirements.target_muscles == ["chest", "triceps"]
        assert requirements.category == "compound"
        assert requirements.supports_1rm is True
        assert requirements.preferred_equipment == ["barbell"]


# ---------------------------------------------------------------------------
# fill_exercise_slot Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFillExerciseSlot:
    """Tests for fill_exercise_slot method."""

    def test_returns_matching_exercise(self, selector, full_gym_equipment):
        """fill_exercise_slot returns an exercise matching requirements."""
        requirements = SlotRequirements(
            movement_pattern="push",
            target_muscles=["chest"],
            category="compound",
        )

        result = selector.fill_exercise_slot(
            requirements=requirements,
            available_equipment=full_gym_equipment,
        )

        assert result is not None
        assert result.get("movement_pattern") == "push"
        assert "chest" in result.get("primary_muscles", [])

    def test_respects_equipment_constraints(self, selector):
        """fill_exercise_slot only returns exercises with available equipment."""
        requirements = SlotRequirements(
            movement_pattern="push",
            target_muscles=["chest"],
        )

        # Only dumbbells available - should not return barbell exercises
        result = selector.fill_exercise_slot(
            requirements=requirements,
            available_equipment=["dumbbells", "bench"],
        )

        assert result is not None
        # Should be incline dumbbell press or similar
        ex_equipment = set(result.get("equipment", []))
        assert "barbell" not in ex_equipment
        if ex_equipment:  # Non-bodyweight exercise
            assert ex_equipment <= {"dumbbells", "bench"}

    def test_excludes_already_selected_exercises(self, selector, full_gym_equipment):
        """fill_exercise_slot excludes exercises in exclude list."""
        requirements = SlotRequirements(
            movement_pattern="push",
            target_muscles=["chest"],
        )

        # First selection
        first = selector.fill_exercise_slot(
            requirements=requirements,
            available_equipment=full_gym_equipment,
        )

        # Second selection excluding first
        second = selector.fill_exercise_slot(
            requirements=requirements,
            available_equipment=full_gym_equipment,
            exclude_exercises=[first["id"]] if first else [],
        )

        if first and second:
            assert first["id"] != second["id"]

    def test_returns_bodyweight_exercise_when_no_equipment(self, selector):
        """fill_exercise_slot returns bodyweight exercises when no equipment."""
        requirements = SlotRequirements(
            movement_pattern="push",
            target_muscles=["chest"],
        )

        result = selector.fill_exercise_slot(
            requirements=requirements,
            available_equipment=[],
        )

        assert result is not None
        # Push-up is bodyweight and targets chest
        ex_equipment = result.get("equipment", [])
        assert ex_equipment == [] or ex_equipment == ["bodyweight"]

    def test_creates_fallback_when_no_match(self, selector):
        """fill_exercise_slot creates fallback when no DB match exists."""
        # Use requirements that won't match any seeded exercises
        requirements = SlotRequirements(
            movement_pattern="rotation",  # No rotation exercises seeded
            target_muscles=["obliques"],
        )

        result = selector.fill_exercise_slot(
            requirements=requirements,
            available_equipment=["barbell"],
        )

        # Should create a fallback placeholder
        if result:
            assert result.get("is_placeholder", False) or "rotation" in result.get("id", "").lower()

    def test_prioritizes_compounds_for_strength(self, selector, full_gym_equipment):
        """fill_exercise_slot prioritizes compound exercises."""
        requirements = SlotRequirements(
            movement_pattern="push",
            category="compound",
        )

        result = selector.fill_exercise_slot(
            requirements=requirements,
            available_equipment=full_gym_equipment,
        )

        assert result is not None
        assert result.get("category") == "compound"

    def test_returns_isolation_when_requested(self, selector, full_gym_equipment):
        """fill_exercise_slot returns isolation exercises when requested."""
        requirements = SlotRequirements(
            movement_pattern="push",
            category="isolation",
        )

        result = selector.fill_exercise_slot(
            requirements=requirements,
            available_equipment=full_gym_equipment,
        )

        assert result is not None
        assert result.get("category") == "isolation"


# ---------------------------------------------------------------------------
# get_alternatives Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetAlternatives:
    """Tests for get_alternatives method."""

    def test_returns_similar_exercises(self, selector, full_gym_equipment):
        """get_alternatives returns exercises similar to the given one."""
        alternatives = selector.get_alternatives(
            exercise_id="barbell-bench-press",
            available_equipment=full_gym_equipment,
            limit=3,
        )

        assert len(alternatives) > 0
        for alt in alternatives:
            assert alt["id"] != "barbell-bench-press"
            # Should have similar movement pattern (push)
            assert alt.get("movement_pattern") == "push"

    def test_respects_equipment_constraints(self, selector):
        """get_alternatives only returns exercises with available equipment."""
        alternatives = selector.get_alternatives(
            exercise_id="barbell-bench-press",
            available_equipment=["dumbbells", "bench"],  # No barbell
            limit=5,
        )

        for alt in alternatives:
            ex_equipment = set(alt.get("equipment", []))
            # Bodyweight or equipment subset
            if ex_equipment:
                assert ex_equipment <= {"dumbbells", "bench"}

    def test_returns_empty_for_unknown_exercise(self, selector, full_gym_equipment):
        """get_alternatives returns empty list for unknown exercise."""
        alternatives = selector.get_alternatives(
            exercise_id="nonexistent-exercise",
            available_equipment=full_gym_equipment,
        )

        assert alternatives == []

    def test_respects_limit(self, selector, full_gym_equipment):
        """get_alternatives respects the limit parameter."""
        alternatives = selector.get_alternatives(
            exercise_id="barbell-bench-press",
            available_equipment=full_gym_equipment,
            limit=2,
        )

        assert len(alternatives) <= 2


# ---------------------------------------------------------------------------
# _normalize_equipment Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNormalizeEquipment:
    """Tests for equipment normalization."""

    def test_normalizes_aliases(self, selector):
        """Equipment aliases are normalized to standard names."""
        normalized = selector._normalize_equipment([
            "dumbbell",  # Should become "dumbbells"
            "cable",     # Should become "cables"
        ])

        assert "dumbbells" in normalized
        assert "cables" in normalized
        assert "dumbbell" not in normalized
        assert "cable" not in normalized

    def test_expands_presets(self, selector):
        """Equipment presets are expanded to full lists."""
        normalized = selector._normalize_equipment(["full_gym"])

        assert "barbell" in normalized
        assert "dumbbells" in normalized
        assert "cables" in normalized

    def test_handles_mixed_input(self, selector):
        """Handles mix of aliases, presets, and standard names."""
        normalized = selector._normalize_equipment([
            "home_basic",  # Preset
            "dumbbell",    # Alias
            "squat_rack",  # Standard name
        ])

        # From preset
        assert "resistance_bands" in normalized
        # From alias
        assert "dumbbells" in normalized
        # Standard name
        assert "squat_rack" in normalized or "rack" in normalized

    def test_handles_empty_list(self, selector):
        """Handles empty equipment list."""
        normalized = selector._normalize_equipment([])

        assert normalized == set()

    def test_preserves_unknown_equipment(self, selector):
        """Unknown equipment names are preserved as-is."""
        normalized = selector._normalize_equipment(["custom_machine"])

        assert "custom_machine" in normalized


# ---------------------------------------------------------------------------
# _create_fallback_exercise Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCreateFallbackExercise:
    """Tests for fallback exercise creation."""

    def test_creates_fallback_with_pattern(self, selector):
        """Creates fallback with movement pattern in name."""
        requirements = SlotRequirements(
            movement_pattern="push",
        )

        fallback = selector._create_fallback_exercise(requirements)

        assert fallback is not None
        assert "push" in fallback.get("id", "").lower()
        assert fallback.get("movement_pattern") == "push"
        assert fallback.get("is_placeholder") is True

    def test_creates_fallback_with_muscle(self, selector):
        """Creates fallback with target muscle in name."""
        requirements = SlotRequirements(
            target_muscles=["chest"],
        )

        fallback = selector._create_fallback_exercise(requirements)

        assert fallback is not None
        assert "chest" in fallback.get("id", "").lower()
        assert "chest" in fallback.get("primary_muscles", [])

    def test_creates_fallback_with_both(self, selector):
        """Creates fallback with both pattern and muscle."""
        requirements = SlotRequirements(
            movement_pattern="hinge",
            target_muscles=["hamstrings"],
        )

        fallback = selector._create_fallback_exercise(requirements)

        assert fallback is not None
        assert "hinge" in fallback.get("id", "").lower()
        assert "hamstrings" in fallback.get("id", "").lower()

    def test_creates_unique_fallback_ids(self, selector):
        """Each fallback has a unique ID (UUID suffix)."""
        requirements = SlotRequirements(
            movement_pattern="push",
            target_muscles=["chest"],
        )

        fallback1 = selector._create_fallback_exercise(requirements)
        fallback2 = selector._create_fallback_exercise(requirements)

        assert fallback1 is not None
        assert fallback2 is not None
        assert fallback1.get("id") != fallback2.get("id")

    def test_returns_none_without_requirements(self, selector):
        """Returns None when no movement pattern or muscles specified."""
        requirements = SlotRequirements()

        fallback = selector._create_fallback_exercise(requirements)

        assert fallback is None


# ---------------------------------------------------------------------------
# Equipment Mapping Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEquipmentMapping:
    """Tests for EQUIPMENT_MAPPING constant."""

    def test_full_gym_contains_essentials(self):
        """full_gym preset contains essential equipment."""
        full_gym = EQUIPMENT_MAPPING["full_gym"]

        assert "barbell" in full_gym
        assert "dumbbells" in full_gym
        assert "cables" in full_gym
        assert "bench" in full_gym

    def test_bodyweight_is_minimal(self):
        """bodyweight preset is minimal."""
        bodyweight = EQUIPMENT_MAPPING["bodyweight"]

        assert len(bodyweight) <= 2
        assert "pull_up_bar" in bodyweight

    def test_home_basic_is_reasonable(self):
        """home_basic preset has reasonable equipment."""
        home_basic = EQUIPMENT_MAPPING["home_basic"]

        assert "dumbbells" in home_basic
        # Should not include heavy gym equipment
        assert "leg_press_machine" not in home_basic
        assert "leg_curl_machine" not in home_basic


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExerciseSelectorIntegration:
    """Integration tests for ExerciseSelector."""

    def test_fills_multiple_slots_without_duplicates(self, selector, full_gym_equipment):
        """Can fill multiple exercise slots without duplicates."""
        requirements = SlotRequirements(
            movement_pattern="push",
            category="compound",
        )

        selected_ids = []
        for _ in range(3):
            ex = selector.fill_exercise_slot(
                requirements=requirements,
                available_equipment=full_gym_equipment,
                exclude_exercises=selected_ids,
            )
            if ex:
                selected_ids.append(ex["id"])

        # All selected exercises should be unique
        assert len(selected_ids) == len(set(selected_ids))

    def test_selects_varied_exercises_for_workout(self, selector, full_gym_equipment):
        """Can select varied exercises for a complete workout."""
        workout_requirements = [
            SlotRequirements(movement_pattern="push", category="compound"),
            SlotRequirements(movement_pattern="push", category="isolation"),
            SlotRequirements(movement_pattern="pull", category="compound"),
            SlotRequirements(movement_pattern="pull", category="isolation"),
        ]

        selected_ids = []
        exercises = []

        for req in workout_requirements:
            ex = selector.fill_exercise_slot(
                requirements=req,
                available_equipment=full_gym_equipment,
                exclude_exercises=selected_ids,
            )
            if ex:
                exercises.append(ex)
                selected_ids.append(ex["id"])

        # Should have variety
        patterns = {ex.get("movement_pattern") for ex in exercises}
        assert len(patterns) >= 2  # At least push and pull
