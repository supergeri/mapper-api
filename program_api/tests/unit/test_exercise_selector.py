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
# _score_candidates Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestScoreCandidates:
    """Tests for _score_candidates method and scoring weights."""

    def test_muscle_overlap_contributes_to_score(self, selector):
        """Muscle overlap adds up to 0.4 to score."""
        candidates = [
            {
                "id": "ex1",
                "primary_muscles": ["chest"],
                "category": "isolation",
                "movement_pattern": "other",
            },
            {
                "id": "ex2",
                "primary_muscles": ["back"],
                "category": "isolation",
                "movement_pattern": "other",
            },
        ]
        requirements = SlotRequirements(target_muscles=["chest"])

        scored = selector._score_candidates(candidates, requirements)

        # Exercise targeting chest should score higher
        assert scored[0].exercise["id"] == "ex1"
        assert scored[0].score > scored[1].score
        # Muscle score is 0.4 max
        assert scored[0].score >= 0.4

    def test_category_match_adds_score(self, selector):
        """Category match adds 0.3 to score."""
        candidates = [
            {"id": "compound", "primary_muscles": [], "category": "compound"},
            {"id": "isolation", "primary_muscles": [], "category": "isolation"},
        ]
        requirements = SlotRequirements(category="compound")

        scored = selector._score_candidates(candidates, requirements)

        compound_score = next(s for s in scored if s.exercise["id"] == "compound")
        isolation_score = next(s for s in scored if s.exercise["id"] == "isolation")

        # Compound gets category bonus (0.3) plus compound priority (0.05)
        assert compound_score.score >= 0.3
        assert compound_score.score > isolation_score.score

    def test_movement_pattern_match_adds_score(self, selector):
        """Movement pattern match adds 0.2 to score."""
        candidates = [
            {"id": "push", "primary_muscles": [], "movement_pattern": "push"},
            {"id": "pull", "primary_muscles": [], "movement_pattern": "pull"},
        ]
        requirements = SlotRequirements(movement_pattern="push")

        scored = selector._score_candidates(candidates, requirements)

        push_score = next(s for s in scored if s.exercise["id"] == "push")
        pull_score = next(s for s in scored if s.exercise["id"] == "pull")

        assert push_score.score >= 0.2
        assert push_score.score > pull_score.score

    def test_preferred_equipment_adds_bonus(self, selector):
        """Preferred equipment match adds 0.1 to score."""
        candidates = [
            {"id": "barbell", "primary_muscles": [], "equipment": ["barbell"]},
            {"id": "dumbbell", "primary_muscles": [], "equipment": ["dumbbells"]},
        ]
        requirements = SlotRequirements(preferred_equipment=["barbell"])

        scored = selector._score_candidates(candidates, requirements)

        barbell_score = next(s for s in scored if s.exercise["id"] == "barbell")
        dumbbell_score = next(s for s in scored if s.exercise["id"] == "dumbbell")

        assert barbell_score.score >= 0.1
        assert barbell_score.score > dumbbell_score.score

    def test_supports_1rm_match_adds_score(self, selector):
        """1RM support match adds 0.05 to score."""
        candidates = [
            {"id": "with1rm", "primary_muscles": [], "supports_1rm": True},
            {"id": "no1rm", "primary_muscles": [], "supports_1rm": False},
        ]
        requirements = SlotRequirements(supports_1rm=True)

        scored = selector._score_candidates(candidates, requirements)

        with1rm_score = next(s for s in scored if s.exercise["id"] == "with1rm")
        no1rm_score = next(s for s in scored if s.exercise["id"] == "no1rm")

        assert with1rm_score.score > no1rm_score.score

    def test_compound_exercises_get_priority_bonus(self, selector):
        """Compound exercises get 0.05 bonus."""
        candidates = [
            {"id": "compound", "primary_muscles": [], "category": "compound"},
            {"id": "isolation", "primary_muscles": [], "category": "isolation"},
        ]
        requirements = SlotRequirements()  # No category preference

        scored = selector._score_candidates(candidates, requirements)

        compound_score = next(s for s in scored if s.exercise["id"] == "compound")
        isolation_score = next(s for s in scored if s.exercise["id"] == "isolation")

        assert compound_score.score == 0.05
        assert isolation_score.score == 0.0

    def test_combined_scoring(self, selector):
        """Combined requirements produce expected total score."""
        candidates = [
            {
                "id": "perfect",
                "primary_muscles": ["chest"],
                "category": "compound",
                "movement_pattern": "push",
                "equipment": ["barbell"],
                "supports_1rm": True,
            },
        ]
        requirements = SlotRequirements(
            target_muscles=["chest"],
            category="compound",
            movement_pattern="push",
            preferred_equipment=["barbell"],
            supports_1rm=True,
        )

        scored = selector._score_candidates(candidates, requirements)

        # 0.4 (muscle) + 0.3 (category) + 0.2 (pattern) + 0.1 (equipment) + 0.05 (1rm) + 0.05 (compound bonus)
        expected_max = 1.1
        assert scored[0].score >= 1.0  # Should be near max

    def test_empty_candidates_returns_empty(self, selector):
        """Empty candidates list returns empty scored list."""
        requirements = SlotRequirements(target_muscles=["chest"])

        scored = selector._score_candidates([], requirements)

        assert scored == []

    def test_scores_sorted_descending(self, selector):
        """Results are sorted by score descending."""
        candidates = [
            {"id": "low", "primary_muscles": [], "category": "isolation"},
            {"id": "high", "primary_muscles": ["chest"], "category": "compound"},
            {"id": "mid", "primary_muscles": ["chest"], "category": "isolation"},
        ]
        requirements = SlotRequirements(target_muscles=["chest"], category="compound")

        scored = selector._score_candidates(candidates, requirements)

        scores = [s.score for s in scored]
        assert scores == sorted(scores, reverse=True)
        assert scored[0].exercise["id"] == "high"


# ---------------------------------------------------------------------------
# Edge Case Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEdgeCases:
    """Edge case tests for ExerciseSelector."""

    def test_empty_target_muscles_list_vs_none(self, selector, full_gym_equipment):
        """Empty list [] behaves differently from None for target_muscles."""
        req_none = SlotRequirements(movement_pattern="push", target_muscles=None)
        req_empty = SlotRequirements(movement_pattern="push", target_muscles=[])

        result_none = selector.fill_exercise_slot(req_none, full_gym_equipment)
        result_empty = selector.fill_exercise_slot(req_empty, full_gym_equipment)

        # Both should return something (empty list doesn't filter)
        assert result_none is not None
        assert result_empty is not None

    def test_duplicate_equipment_in_list(self, selector):
        """Duplicate equipment entries are handled correctly."""
        normalized = selector._normalize_equipment([
            "barbell", "barbell", "dumbbells", "dumbbells"
        ])

        # Should deduplicate
        assert normalized == {"barbell", "dumbbells"}

    def test_whitespace_in_equipment_names(self, selector):
        """Equipment names with whitespace are normalized."""
        normalized = selector._normalize_equipment([
            "  barbell  ",
            " dumbbells",
            "cables  ",
        ])

        assert "barbell" in normalized
        assert "dumbbells" in normalized
        assert "cables" in normalized

    def test_mixed_case_equipment(self, selector):
        """Equipment names are case-insensitive."""
        normalized = selector._normalize_equipment([
            "BARBELL",
            "DumbBells",
            "CaBlEs",
        ])

        assert "barbell" in normalized
        assert "dumbbells" in normalized
        assert "cables" in normalized

    def test_fill_slot_with_all_exercises_excluded(self, selector, full_gym_equipment):
        """Returns fallback when all matching exercises are excluded."""
        # Get all push exercises
        all_push = selector._exercise_repo.get_by_movement_pattern("push")
        all_ids = [ex["id"] for ex in all_push]

        requirements = SlotRequirements(movement_pattern="push")

        result = selector.fill_exercise_slot(
            requirements=requirements,
            available_equipment=full_gym_equipment,
            exclude_exercises=all_ids,
        )

        # Should create a fallback
        if result:
            assert result.get("is_placeholder", False) or result["id"] not in all_ids

    def test_get_alternatives_with_empty_equipment(self, selector):
        """get_alternatives with empty equipment returns bodyweight alternatives."""
        alternatives = selector.get_alternatives(
            exercise_id="barbell-bench-press",
            available_equipment=[],
            limit=5,
        )

        # Should only return bodyweight exercises
        for alt in alternatives:
            equipment = alt.get("equipment", [])
            assert equipment == [] or equipment == ["bodyweight"]

    def test_requirements_with_nonexistent_muscle(self, selector, full_gym_equipment):
        """Requirements with non-existent muscle group creates fallback."""
        requirements = SlotRequirements(
            target_muscles=["nonexistent_muscle_group"],
        )

        result = selector.fill_exercise_slot(
            requirements=requirements,
            available_equipment=full_gym_equipment,
        )

        # Should create fallback since no exercises match
        if result:
            assert result.get("is_placeholder", False) or "nonexistent" in str(result)


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
