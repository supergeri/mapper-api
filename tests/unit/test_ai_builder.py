"""
Unit tests for AI Builder service (parsing logic and rule-based defaults).

Part of AMA-446: AI Builder API Endpoint
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.services.ai_builder import (
    AIBuilderService,
    AIBuildResult,
    DEFAULT_REST_PERIODS,
    DEFAULT_REPS,
    DEFAULT_SETS,
    ExerciseSuggestion,
    GarminCompatibility,
)
from domain.models import Workout, Block, Exercise


class TestAIBuilderRuleBasedDefaults:
    """Test rule-based default filling when LLM is unavailable."""

    def setup_method(self):
        """Create service without LLM clients."""
        self.service = AIBuilderService(
            openai_client=None,
            anthropic_client=None,
        )

    def test_basic_build_with_exercises(self):
        """Build a workout from basic exercise list."""
        result = self.service.build(
            workout_type="strength",
            exercises=[
                {"name": "Bench Press"},
                {"name": "Squat"},
                {"name": "Deadlift"},
            ],
        )

        assert result.workout is not None
        assert result.error is None
        assert len(result.workout.blocks) == 1
        assert len(result.workout.blocks[0].exercises) == 3
        assert result.llm_used is None  # No LLM available

    def test_strength_defaults(self):
        """Strength workouts get appropriate defaults."""
        result = self.service.build(
            workout_type="strength",
            exercises=[{"name": "Bench Press"}],
        )

        ex = result.workout.blocks[0].exercises[0]
        assert ex.sets == DEFAULT_SETS["strength"]
        assert ex.reps == DEFAULT_REPS["strength"]
        assert ex.rest_seconds == DEFAULT_REST_PERIODS["strength"]

    def test_hypertrophy_defaults(self):
        """Hypertrophy workouts get appropriate defaults."""
        result = self.service.build(
            workout_type="hypertrophy",
            exercises=[{"name": "Bicep Curl"}],
        )

        ex = result.workout.blocks[0].exercises[0]
        assert ex.sets == DEFAULT_SETS["hypertrophy"]
        assert ex.reps == DEFAULT_REPS["hypertrophy"]
        assert ex.rest_seconds == DEFAULT_REST_PERIODS["hypertrophy"]

    def test_hiit_defaults(self):
        """HIIT workouts get appropriate defaults."""
        result = self.service.build(
            workout_type="hiit",
            exercises=[{"name": "Burpees"}],
        )

        ex = result.workout.blocks[0].exercises[0]
        assert ex.sets == DEFAULT_SETS["hiit"]
        assert ex.reps == DEFAULT_REPS["hiit"]
        assert ex.rest_seconds == DEFAULT_REST_PERIODS["hiit"]

    def test_preserves_provided_values(self):
        """Provided values should not be overwritten by defaults."""
        result = self.service.build(
            workout_type="strength",
            exercises=[{
                "name": "Bench Press",
                "sets": 8,
                "reps": 3,
                "rest_seconds": 180,
            }],
        )

        ex = result.workout.blocks[0].exercises[0]
        assert ex.sets == 8
        assert ex.reps == 3
        assert ex.rest_seconds == 180

    def test_user_preference_overrides(self):
        """User preferences should override workout type defaults."""
        result = self.service.build(
            workout_type="strength",
            exercises=[{"name": "Squat"}],
            user_preferences={
                "rest_seconds": 300,
                "default_reps": 1,
                "default_sets": 1,
            },
        )

        ex = result.workout.blocks[0].exercises[0]
        assert ex.sets == 1
        assert ex.reps == 1
        assert ex.rest_seconds == 300

    def test_circuit_format(self):
        """Circuit format should set block type."""
        result = self.service.build(
            workout_type="circuit",
            format="circuit",
            rounds=3,
            exercises=[
                {"name": "Pushups"},
                {"name": "Squats"},
            ],
        )

        block = result.workout.blocks[0]
        assert block.type.value == "circuit"
        assert block.rounds == 3

    def test_superset_format(self):
        """Superset format should set block type."""
        result = self.service.build(
            workout_type="hypertrophy",
            format="superset",
            exercises=[
                {"name": "Bench Press"},
                {"name": "Bent Over Row"},
            ],
        )

        block = result.workout.blocks[0]
        assert block.type.value == "superset"

    def test_empty_exercises_generates_placeholder(self):
        """Empty exercise list should still produce a valid workout."""
        result = self.service.build(
            workout_type="strength",
            exercises=[],
        )

        assert result.workout is not None
        assert len(result.workout.blocks) == 1
        assert len(result.workout.blocks[0].exercises) >= 1

    def test_exercise_with_duration(self):
        """Timed exercises should use duration instead of reps."""
        result = self.service.build(
            workout_type="strength",
            exercises=[{
                "name": "Plank",
                "duration_seconds": 60,
            }],
        )

        ex = result.workout.blocks[0].exercises[0]
        assert ex.duration_seconds == 60

    def test_exercise_with_load(self):
        """Exercises with load should have Load object."""
        result = self.service.build(
            workout_type="strength",
            exercises=[{
                "name": "Squat",
                "load_value": 225,
                "load_unit": "lb",
            }],
        )

        ex = result.workout.blocks[0].exercises[0]
        assert ex.load is not None
        assert ex.load.value == 225
        assert ex.load.unit == "lb"

    def test_source_url_in_metadata(self):
        """Source URL should be included in workout metadata."""
        result = self.service.build(
            workout_type="strength",
            exercises=[{"name": "Squat"}],
            source_url="https://example.com/workout",
        )

        assert result.workout.metadata.source_url == "https://example.com/workout"


class TestSuggestions:
    """Test suggestion generation."""

    def setup_method(self):
        self.service = AIBuilderService(
            openai_client=None,
            anthropic_client=None,
        )

    def test_suggestions_for_missing_rest(self):
        """Should suggest rest periods when not provided."""
        result = self.service.build(
            workout_type="strength",
            exercises=[{"name": "Bench Press"}],
        )

        rest_suggestions = [s for s in result.suggestions if s.field == "rest_seconds"]
        assert len(rest_suggestions) > 0
        assert rest_suggestions[0].suggested_value == DEFAULT_REST_PERIODS["strength"]

    def test_suggestions_for_missing_sets(self):
        """Should suggest sets when not provided."""
        result = self.service.build(
            workout_type="strength",
            exercises=[{"name": "Bench Press"}],
        )

        set_suggestions = [s for s in result.suggestions if s.field == "sets"]
        assert len(set_suggestions) > 0

    def test_suggestions_for_missing_reps(self):
        """Should suggest reps when not provided."""
        result = self.service.build(
            workout_type="strength",
            exercises=[{"name": "Bench Press"}],
        )

        rep_suggestions = [s for s in result.suggestions if s.field == "reps"]
        assert len(rep_suggestions) > 0

    def test_no_suggestions_when_all_provided(self):
        """Should not suggest values that were already provided."""
        result = self.service.build(
            workout_type="strength",
            exercises=[{
                "name": "Bench Press",
                "sets": 5,
                "reps": 5,
                "rest_seconds": 120,
            }],
        )

        # Should have no suggestions for sets/reps/rest (only maybe canonical_name)
        field_suggestions = [s for s in result.suggestions
                           if s.field in ("sets", "reps", "rest_seconds")]
        assert len(field_suggestions) == 0


class TestGarminCompatibility:
    """Test Garmin compatibility checking."""

    def setup_method(self):
        self.service = AIBuilderService(
            openai_client=None,
            anthropic_client=None,
        )

    def test_garmin_compatibility_returned(self):
        """Garmin compatibility should be included in result."""
        result = self.service.build(
            workout_type="strength",
            exercises=[{"name": "Bench Press"}],
        )

        assert result.garmin_compatibility is not None
        assert isinstance(result.garmin_compatibility.warnings, list)
        assert isinstance(result.garmin_compatibility.unsupported_exercises, list)
        assert isinstance(result.garmin_compatibility.mapped_exercises, dict)

    def test_build_time_tracked(self):
        """Build time should be tracked in milliseconds."""
        result = self.service.build(
            workout_type="strength",
            exercises=[{"name": "Squat"}],
        )

        assert result.build_time_ms >= 0


class TestCanonicalNameResolution:
    """Test exercise name resolution to canonical names."""

    def setup_method(self):
        self.service = AIBuilderService(
            openai_client=None,
            anthropic_client=None,
        )

    @patch("backend.services.ai_builder.find_garmin_exercise")
    def test_canonical_name_set_on_match(self, mock_find):
        """Canonical name should be set when match is found."""
        mock_find.return_value = ("Barbell Bench Press", 0.95)

        result = self.service.build(
            workout_type="strength",
            exercises=[{"name": "Bench Press"}],
        )

        ex = result.workout.blocks[0].exercises[0]
        assert ex.canonical_name == "Barbell Bench Press"

    @patch("backend.services.ai_builder.find_garmin_exercise")
    def test_canonical_name_none_on_low_confidence(self, mock_find):
        """Canonical name should be None when confidence is too low."""
        mock_find.return_value = ("Some Exercise", 0.3)

        result = self.service.build(
            workout_type="strength",
            exercises=[{"name": "Made Up Exercise"}],
        )

        ex = result.workout.blocks[0].exercises[0]
        assert ex.canonical_name is None


class TestLLMIntegration:
    """Test LLM client integration (with mocks)."""

    def test_openai_used_when_available(self):
        """Should try OpenAI first when client is available."""
        mock_openai = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "title": "LLM Workout",
            "description": "Test",
            "workout_type": "strength",
            "blocks": [{
                "label": "Main",
                "type": "straight",
                "exercises": [{
                    "name": "Barbell Back Squat",
                    "sets": 5,
                    "reps": 5,
                    "rest_seconds": 180,
                }],
            }],
        })
        mock_openai.chat.completions.create.return_value = mock_response

        service = AIBuilderService(openai_client=mock_openai)
        result = service.build(
            workout_type="strength",
            exercises=[{"name": "Squat"}],
        )

        assert result.llm_used == "gpt-4o-mini"
        assert result.workout.title == "LLM Workout"
        mock_openai.chat.completions.create.assert_called_once()

    def test_anthropic_fallback_on_openai_failure(self):
        """Should fall back to Anthropic when OpenAI fails."""
        mock_openai = MagicMock()
        mock_openai.chat.completions.create.side_effect = Exception("OpenAI error")

        mock_anthropic = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = json.dumps({
            "title": "Claude Workout",
            "description": "Test",
            "workout_type": "strength",
            "blocks": [{
                "label": "Main",
                "type": "straight",
                "exercises": [{
                    "name": "Barbell Back Squat",
                    "sets": 5,
                    "reps": 5,
                    "rest_seconds": 180,
                }],
            }],
        })
        mock_anthropic.messages.create.return_value = mock_response

        service = AIBuilderService(
            openai_client=mock_openai,
            anthropic_client=mock_anthropic,
        )
        result = service.build(
            workout_type="strength",
            exercises=[{"name": "Squat"}],
        )

        assert result.llm_used == "claude-3-haiku"
        assert result.workout.title == "Claude Workout"

    def test_rule_based_fallback_when_no_llm(self):
        """Should use rule-based defaults when no LLM is available."""
        service = AIBuilderService()
        result = service.build(
            workout_type="strength",
            exercises=[{"name": "Squat"}],
        )

        assert result.llm_used is None
        assert result.workout is not None

    def test_rule_based_fallback_when_both_llm_fail(self):
        """Should use rule-based defaults when both LLMs fail."""
        mock_openai = MagicMock()
        mock_openai.chat.completions.create.side_effect = Exception("fail")

        mock_anthropic = MagicMock()
        mock_anthropic.messages.create.side_effect = Exception("fail")

        service = AIBuilderService(
            openai_client=mock_openai,
            anthropic_client=mock_anthropic,
        )
        result = service.build(
            workout_type="strength",
            exercises=[{"name": "Squat"}],
        )

        assert result.llm_used is None
        assert result.workout is not None


class TestWorkoutOutputSchema:
    """Test that output matches unified workout schema."""

    def setup_method(self):
        self.service = AIBuilderService()

    def test_output_is_valid_workout(self):
        """Output should be a valid Workout domain model."""
        result = self.service.build(
            workout_type="strength",
            exercises=[
                {"name": "Squat", "sets": 5, "reps": 5},
                {"name": "Bench Press", "sets": 4, "reps": 8},
            ],
        )

        workout = result.workout
        assert isinstance(workout, Workout)
        assert workout.title
        assert len(workout.blocks) >= 1

        for block in workout.blocks:
            assert isinstance(block, Block)
            for ex in block.exercises:
                assert isinstance(ex, Exercise)
                assert ex.name

    def test_output_serializable(self):
        """Output workout should be JSON-serializable."""
        result = self.service.build(
            workout_type="strength",
            exercises=[{"name": "Squat"}],
        )

        json_str = result.workout.model_dump_json()
        assert json_str
        parsed = json.loads(json_str)
        assert "title" in parsed
        assert "blocks" in parsed
