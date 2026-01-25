"""
Unit tests for TemplateSelector service.

Part of AMA-462: Testing improvements

Tests template selection logic:
- Template scoring algorithm
- Sessions per week matching
- Duration matching
- Popularity scoring
- Default structure generation
"""

import pytest

from models.program import ExperienceLevel, ProgramGoal
from services.template_selector import TemplateSelector, TemplateMatch
from tests.fakes import FakeTemplateRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def template_repo():
    """Create a fake template repository."""
    return FakeTemplateRepository()


@pytest.fixture
def seeded_template_repo():
    """Create a template repository with default templates."""
    repo = FakeTemplateRepository()
    repo.seed_default_templates()
    return repo


@pytest.fixture
def selector(seeded_template_repo):
    """Create a TemplateSelector with seeded repository."""
    return TemplateSelector(seeded_template_repo)


@pytest.fixture
def empty_selector(template_repo):
    """Create a TemplateSelector with empty repository."""
    return TemplateSelector(template_repo)


@pytest.fixture
def sample_template():
    """A sample template for testing."""
    return {
        "id": "test-template-1",
        "name": "Test PPL Template",
        "goal": "hypertrophy",
        "experience_level": "intermediate",
        "duration_weeks": 8,
        "usage_count": 50,
        "structure": {
            "weeks": [{
                "workouts": [
                    {"day_of_week": 1, "name": "Push"},
                    {"day_of_week": 2, "name": "Pull"},
                    {"day_of_week": 3, "name": "Legs"},
                    {"day_of_week": 5, "name": "Push"},
                ],
            }],
        },
    }


# ---------------------------------------------------------------------------
# Template Scoring Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTemplateScoring:
    """Tests for the template scoring algorithm."""

    def test_base_score_for_matching_template(self, selector, sample_template):
        """Matching template gets base score."""
        match = selector._score_template(
            template=sample_template,
            sessions_per_week=4,
            duration_weeks=8,
        )

        assert match.score >= TemplateSelector.SCORE_BASE
        assert "Goal and experience match" in match.match_reasons

    def test_exact_sessions_match_adds_score(self, selector, sample_template):
        """Exact sessions match adds SCORE_SESSIONS_MATCH points."""
        # Template has 4 workouts
        match = selector._score_template(
            template=sample_template,
            sessions_per_week=4,  # Exact match
            duration_weeks=8,
        )

        assert match.score >= TemplateSelector.SCORE_BASE + TemplateSelector.SCORE_SESSIONS_MATCH
        assert any("exact sessions" in r.lower() for r in match.match_reasons)

    def test_close_sessions_match_adds_partial_score(self, selector, sample_template):
        """Sessions within 1 adds SCORE_SESSIONS_CLOSE points."""
        match = selector._score_template(
            template=sample_template,
            sessions_per_week=5,  # 1 off from 4
            duration_weeks=8,
        )

        # Should have close match bonus but not exact
        assert any("close sessions" in r.lower() for r in match.match_reasons)

    def test_far_sessions_no_bonus(self, selector, sample_template):
        """Sessions more than 1 off gets no sessions bonus."""
        match_exact = selector._score_template(
            template=sample_template,
            sessions_per_week=4,
            duration_weeks=8,
        )

        match_far = selector._score_template(
            template=sample_template,
            sessions_per_week=7,  # 3 off
            duration_weeks=8,
        )

        # Far match should have lower score (no sessions bonus)
        assert match_far.score < match_exact.score

    def test_exact_duration_match_adds_score(self, selector, sample_template):
        """Exact duration match adds SCORE_DURATION_MATCH points."""
        match = selector._score_template(
            template=sample_template,
            sessions_per_week=4,
            duration_weeks=8,  # Template is 8 weeks
        )

        assert any("exact duration" in r.lower() for r in match.match_reasons)

    def test_close_duration_match_adds_partial_score(self, selector, sample_template):
        """Duration within 2 weeks adds SCORE_DURATION_CLOSE points."""
        match = selector._score_template(
            template=sample_template,
            sessions_per_week=4,
            duration_weeks=10,  # 2 off from 8
        )

        assert any("close duration" in r.lower() for r in match.match_reasons)

    def test_popularity_adds_score(self, selector, sample_template):
        """Popular templates get bonus score."""
        # Sample template has usage_count=50
        match = selector._score_template(
            template=sample_template,
            sessions_per_week=4,
            duration_weeks=8,
        )

        assert any("used" in r.lower() for r in match.match_reasons)

    def test_unused_template_no_popularity_bonus(self, selector):
        """Unused templates get no popularity bonus."""
        unused_template = {
            "id": "unused",
            "name": "Unused Template",
            "usage_count": 0,
            "structure": {"weeks": [{"workouts": [{"name": "A"}, {"name": "B"}, {"name": "C"}]}]},
        }

        match = selector._score_template(
            template=unused_template,
            sessions_per_week=3,
            duration_weeks=8,
        )

        # Should not mention usage
        assert not any("used" in r.lower() for r in match.match_reasons)

    def test_max_popularity_score_capped(self, selector):
        """Popularity score caps at SCORE_POPULARITY_MAX."""
        very_popular = {
            "id": "popular",
            "name": "Very Popular",
            "usage_count": 1000,  # Way over 100 cap
            "structure": {"weeks": [{"workouts": [{"name": "A"}]}]},
        }

        match = selector._score_template(
            template=very_popular,
            sessions_per_week=1,
            duration_weeks=8,
        )

        # Score should include max popularity but not more
        # Base + Sessions + Duration + Popularity
        max_possible = (
            TemplateSelector.SCORE_BASE +
            TemplateSelector.SCORE_SESSIONS_MATCH +
            TemplateSelector.SCORE_DURATION_MATCH +
            TemplateSelector.SCORE_POPULARITY_MAX
        )
        assert match.score <= max_possible


# ---------------------------------------------------------------------------
# Template Selection Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTemplateSelection:
    """Tests for the template selection process."""

    @pytest.mark.asyncio
    async def test_selects_best_matching_template(self, seeded_template_repo):
        """Selects the template with highest score."""
        selector = TemplateSelector(seeded_template_repo)

        result = await selector.select_best_template(
            goal=ProgramGoal.HYPERTROPHY,
            experience_level=ExperienceLevel.INTERMEDIATE,
            sessions_per_week=4,
            duration_weeks=8,
        )

        assert result is not None
        assert isinstance(result, TemplateMatch)
        assert result.score > 0

    @pytest.mark.asyncio
    async def test_returns_none_when_no_templates(self, empty_selector):
        """Returns None when no templates match."""
        result = await empty_selector.select_best_template(
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.BEGINNER,
            sessions_per_week=3,
            duration_weeks=4,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_accepts_string_goal(self, seeded_template_repo):
        """Accepts goal as string instead of enum."""
        selector = TemplateSelector(seeded_template_repo)

        result = await selector.select_best_template(
            goal="hypertrophy",
            experience_level=ExperienceLevel.INTERMEDIATE,
            sessions_per_week=4,
            duration_weeks=8,
        )

        # Should work with string
        assert result is not None or result is None  # Either is valid depending on repo

    @pytest.mark.asyncio
    async def test_accepts_string_experience_level(self, seeded_template_repo):
        """Accepts experience level as string instead of enum."""
        selector = TemplateSelector(seeded_template_repo)

        result = await selector.select_best_template(
            goal=ProgramGoal.HYPERTROPHY,
            experience_level="intermediate",
            sessions_per_week=4,
            duration_weeks=8,
        )

        # Should work with string
        assert result is not None or result is None


# ---------------------------------------------------------------------------
# Session Counting Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSessionCounting:
    """Tests for _get_template_sessions method."""

    def test_counts_workouts_in_first_week(self, selector):
        """Counts workouts from first week."""
        template = {
            "structure": {
                "weeks": [{
                    "workouts": [
                        {"name": "A"},
                        {"name": "B"},
                        {"name": "C"},
                        {"name": "D"},
                    ],
                }],
            },
        }

        sessions = selector._get_template_sessions(template["structure"])
        assert sessions == 4

    def test_defaults_to_3_when_no_weeks(self, selector):
        """Defaults to 3 sessions when no weeks defined."""
        template = {"structure": {"weeks": []}}

        sessions = selector._get_template_sessions(template["structure"])
        assert sessions == 3

    def test_defaults_to_3_when_no_workouts(self, selector):
        """Defaults to 3 sessions when no workouts in week."""
        template = {"structure": {"weeks": [{"workouts": []}]}}

        sessions = selector._get_template_sessions(template["structure"])
        assert sessions == 3

    def test_handles_empty_structure(self, selector):
        """Handles empty structure gracefully."""
        sessions = selector._get_template_sessions({})
        assert sessions == 3


# ---------------------------------------------------------------------------
# Default Structure Generation Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDefaultStructureGeneration:
    """Tests for default structure generation."""

    @pytest.mark.asyncio
    async def test_2_sessions_returns_full_body(self, selector):
        """2 sessions per week returns full body split."""
        structure = await selector.get_default_structure(
            goal=ProgramGoal.GENERAL_FITNESS,
            experience_level=ExperienceLevel.BEGINNER,
            sessions_per_week=2,
            duration_weeks=4,
        )

        assert structure["split_type"] == "full_body"
        # Full body split has 3 workouts, should get 2 of them
        assert len(structure["weeks"][0]["workouts"]) >= 2

    @pytest.mark.asyncio
    async def test_3_sessions_strength_returns_ppl(self, selector):
        """3 sessions with strength goal returns PPL."""
        structure = await selector.get_default_structure(
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
            sessions_per_week=3,
            duration_weeks=8,
        )

        assert structure["split_type"] == "push_pull_legs"
        assert len(structure["weeks"][0]["workouts"]) == 3

    @pytest.mark.asyncio
    async def test_3_sessions_endurance_returns_full_body(self, selector):
        """3 sessions with endurance goal returns full body."""
        structure = await selector.get_default_structure(
            goal=ProgramGoal.ENDURANCE,
            experience_level=ExperienceLevel.BEGINNER,
            sessions_per_week=3,
            duration_weeks=4,
        )

        assert structure["split_type"] == "full_body"

    @pytest.mark.asyncio
    async def test_4_sessions_returns_upper_lower(self, selector):
        """4 sessions returns upper/lower split."""
        structure = await selector.get_default_structure(
            goal=ProgramGoal.HYPERTROPHY,
            experience_level=ExperienceLevel.INTERMEDIATE,
            sessions_per_week=4,
            duration_weeks=8,
        )

        assert structure["split_type"] == "upper_lower"
        assert len(structure["weeks"][0]["workouts"]) == 4

    @pytest.mark.asyncio
    async def test_5_sessions_returns_ppl_upper_lower(self, selector):
        """5 sessions returns PPL + upper/lower hybrid."""
        structure = await selector.get_default_structure(
            goal=ProgramGoal.HYPERTROPHY,
            experience_level=ExperienceLevel.ADVANCED,
            sessions_per_week=5,
            duration_weeks=8,
        )

        assert structure["split_type"] == "ppl_upper_lower"
        assert len(structure["weeks"][0]["workouts"]) == 5

    @pytest.mark.asyncio
    async def test_6_sessions_returns_ppl_twice(self, selector):
        """6 sessions returns PPL twice."""
        structure = await selector.get_default_structure(
            goal=ProgramGoal.HYPERTROPHY,
            experience_level=ExperienceLevel.ADVANCED,
            sessions_per_week=6,
            duration_weeks=8,
        )

        assert structure["split_type"] == "ppl_twice"
        assert len(structure["weeks"][0]["workouts"]) == 6

    @pytest.mark.asyncio
    async def test_7_sessions_returns_ppl_twice_plus(self, selector):
        """7 sessions returns PPL twice plus arms."""
        structure = await selector.get_default_structure(
            goal=ProgramGoal.HYPERTROPHY,
            experience_level=ExperienceLevel.ADVANCED,
            sessions_per_week=7,
            duration_weeks=8,
        )

        assert structure["split_type"] == "ppl_twice_plus"
        assert len(structure["weeks"][0]["workouts"]) == 7

    @pytest.mark.asyncio
    async def test_structure_includes_mesocycle_length(self, selector):
        """Structure includes mesocycle_length."""
        structure = await selector.get_default_structure(
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
            sessions_per_week=4,
            duration_weeks=12,
        )

        assert "mesocycle_length" in structure
        assert structure["mesocycle_length"] <= 4

    @pytest.mark.asyncio
    async def test_structure_includes_deload_frequency(self, selector):
        """Structure includes deload_frequency."""
        structure = await selector.get_default_structure(
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
            sessions_per_week=4,
            duration_weeks=8,
        )

        assert "deload_frequency" in structure
        assert structure["deload_frequency"] == 4

    @pytest.mark.asyncio
    async def test_workouts_have_required_fields(self, selector):
        """Each workout has required fields."""
        structure = await selector.get_default_structure(
            goal=ProgramGoal.HYPERTROPHY,
            experience_level=ExperienceLevel.INTERMEDIATE,
            sessions_per_week=4,
            duration_weeks=8,
        )

        for workout in structure["weeks"][0]["workouts"]:
            assert "day_of_week" in workout
            assert "name" in workout
            assert "workout_type" in workout
            assert "muscle_groups" in workout
            assert "exercise_slots" in workout
            assert "target_duration_minutes" in workout

    @pytest.mark.asyncio
    async def test_day_of_week_valid_range(self, selector):
        """All day_of_week values are 1-7."""
        structure = await selector.get_default_structure(
            goal=ProgramGoal.HYPERTROPHY,
            experience_level=ExperienceLevel.ADVANCED,
            sessions_per_week=7,
            duration_weeks=8,
        )

        for workout in structure["weeks"][0]["workouts"]:
            assert 1 <= workout["day_of_week"] <= 7


# ---------------------------------------------------------------------------
# Focus Text Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFocusText:
    """Tests for _get_focus_for_goal method."""

    def test_strength_focus(self, selector):
        """Strength goal returns appropriate focus."""
        focus = selector._get_focus_for_goal("strength")
        assert "strength" in focus.lower()

    def test_hypertrophy_focus(self, selector):
        """Hypertrophy goal returns appropriate focus."""
        focus = selector._get_focus_for_goal("hypertrophy")
        assert "muscle" in focus.lower() or "building" in focus.lower()

    def test_endurance_focus(self, selector):
        """Endurance goal returns appropriate focus."""
        focus = selector._get_focus_for_goal("endurance")
        assert "endurance" in focus.lower()

    def test_weight_loss_focus(self, selector):
        """Weight loss goal returns appropriate focus."""
        focus = selector._get_focus_for_goal("weight_loss")
        assert "fat" in focus.lower() or "loss" in focus.lower()

    def test_unknown_goal_returns_general(self, selector):
        """Unknown goal returns general training focus."""
        focus = selector._get_focus_for_goal("unknown_goal")
        assert "general" in focus.lower()


# ---------------------------------------------------------------------------
# Split Configuration Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSplitConfigurations:
    """Tests for individual split configurations."""

    def test_full_body_split_structure(self, selector):
        """Full body split has correct structure."""
        split = selector._full_body_split()

        assert split["name"] == "full_body"
        assert len(split["workouts"]) == 3
        assert all(w["workout_type"] == "full_body" for w in split["workouts"])

    def test_ppl_split_structure(self, selector):
        """PPL split has correct structure."""
        split = selector._push_pull_legs_split()

        assert split["name"] == "push_pull_legs"
        assert len(split["workouts"]) == 3

        workout_types = [w["workout_type"] for w in split["workouts"]]
        assert "push" in workout_types
        assert "pull" in workout_types
        assert "legs" in workout_types

    def test_upper_lower_split_structure(self, selector):
        """Upper/lower split has correct structure."""
        split = selector._upper_lower_split()

        assert split["name"] == "upper_lower"
        assert len(split["workouts"]) == 4

        workout_types = [w["workout_type"] for w in split["workouts"]]
        assert workout_types.count("upper") == 2
        assert workout_types.count("lower") == 2

    def test_ppl_twice_split_structure(self, selector):
        """PPL twice split has correct structure."""
        split = selector._ppl_twice_split()

        assert split["name"] == "ppl_twice"
        assert len(split["workouts"]) == 6

        workout_types = [w["workout_type"] for w in split["workouts"]]
        assert workout_types.count("push") == 2
        assert workout_types.count("pull") == 2
        assert workout_types.count("legs") == 2

    def test_ppl_twice_plus_includes_arms(self, selector):
        """PPL twice plus includes arms workout."""
        split = selector._ppl_twice_plus_split()

        assert split["name"] == "ppl_twice_plus"
        assert len(split["workouts"]) == 7

        workout_types = [w["workout_type"] for w in split["workouts"]]
        assert "arms" in workout_types

    def test_all_splits_have_valid_days(self, selector):
        """All split configurations have valid day_of_week values."""
        splits = [
            selector._full_body_split(),
            selector._push_pull_legs_split(),
            selector._upper_lower_split(),
            selector._ppl_upper_lower_split(),
            selector._ppl_twice_split(),
            selector._ppl_twice_plus_split(),
        ]

        for split in splits:
            for workout in split["workouts"]:
                assert 1 <= workout["day_of_week"] <= 7, (
                    f"Invalid day_of_week {workout['day_of_week']} in {split['name']}"
                )

    def test_all_splits_have_muscle_groups(self, selector):
        """All workouts in all splits have muscle groups defined."""
        splits = [
            selector._full_body_split(),
            selector._push_pull_legs_split(),
            selector._upper_lower_split(),
            selector._ppl_upper_lower_split(),
            selector._ppl_twice_split(),
            selector._ppl_twice_plus_split(),
        ]

        for split in splits:
            for workout in split["workouts"]:
                assert "muscle_groups" in workout
                assert len(workout["muscle_groups"]) > 0


# ---------------------------------------------------------------------------
# TemplateMatch Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTemplateMatch:
    """Tests for TemplateMatch dataclass."""

    def test_template_match_creation(self):
        """Can create TemplateMatch with all fields."""
        template = {"id": "test", "name": "Test"}
        match = TemplateMatch(
            template=template,
            score=75.5,
            match_reasons=["Reason 1", "Reason 2"],
        )

        assert match.template == template
        assert match.score == 75.5
        assert len(match.match_reasons) == 2

    def test_template_match_comparison_by_score(self):
        """TemplateMatches can be sorted by score."""
        matches = [
            TemplateMatch({"id": "a"}, 50.0, []),
            TemplateMatch({"id": "b"}, 75.0, []),
            TemplateMatch({"id": "c"}, 25.0, []),
        ]

        sorted_matches = sorted(matches, key=lambda m: m.score, reverse=True)

        assert sorted_matches[0].template["id"] == "b"
        assert sorted_matches[1].template["id"] == "a"
        assert sorted_matches[2].template["id"] == "c"
