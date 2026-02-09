"""
Unit tests for domain converters.

Part of AMA-390: Add converters for ingest and block formats

Tests for:
- ingest_to_workout
- blocks_to_workout
- db_row_to_workout
- workout_to_db_row
"""

from datetime import datetime, timezone

import pytest

from backend.parsers.models import ParsedExercise, ParsedWorkout
from backend.adapters.blocks_to_workoutkit import to_workoutkit
from domain.converters import (
    blocks_to_workout,
    db_row_to_workout,
    ingest_to_workout,
    workout_to_db_row,
)
from domain.models import Block, BlockType, Exercise, Load, Workout, WorkoutMetadata, WorkoutSource


# =============================================================================
# ingest_to_workout tests
# =============================================================================


@pytest.mark.unit
class TestIngestToWorkout:
    """Tests for ingest_to_workout converter."""

    def test_basic_workout(self):
        """Convert basic ParsedWorkout with exercises."""
        parsed = ParsedWorkout(
            name="Test Workout",
            exercises=[
                ParsedExercise(raw_name="Squat", sets=3, reps="10"),
                ParsedExercise(raw_name="Bench Press", sets=3, reps="8"),
            ],
        )

        workout = ingest_to_workout(parsed)

        assert workout.title == "Test Workout"
        assert workout.total_exercises == 2
        assert workout.exercise_names == ["Squat", "Bench Press"]

    def test_with_description(self):
        """Convert workout with description."""
        parsed = ParsedWorkout(
            name="Full Body",
            description="A complete full body workout",
            exercises=[
                ParsedExercise(raw_name="Deadlift", sets=5, reps="5"),
            ],
        )

        workout = ingest_to_workout(parsed)

        assert workout.description == "A complete full body workout"

    def test_preserves_reps_as_string(self):
        """Complex rep schemes are preserved as strings."""
        parsed = ParsedWorkout(
            name="Complex Reps",
            exercises=[
                ParsedExercise(raw_name="Pause Squat", sets=5, reps="3+1"),
                ParsedExercise(raw_name="AMRAP Set", sets=1, reps="AMRAP"),
            ],
        )

        workout = ingest_to_workout(parsed)

        # Both exercises end up in the same block (no superset grouping)
        assert workout.blocks[0].exercises[0].reps == "3+1"
        assert workout.blocks[0].exercises[1].reps == "AMRAP"

    def test_duration_from_reps_string(self):
        """Duration parsed from reps like '60s'."""
        parsed = ParsedWorkout(
            name="Timed",
            exercises=[
                ParsedExercise(raw_name="Plank", sets=3, reps="60s"),
            ],
        )

        workout = ingest_to_workout(parsed)

        exercise = workout.blocks[0].exercises[0]
        assert exercise.duration_seconds == 60
        assert exercise.reps is None

    def test_weight_parsing(self):
        """Weight and unit are converted to Load."""
        parsed = ParsedWorkout(
            name="Heavy",
            exercises=[
                ParsedExercise(raw_name="Squat", sets=5, reps="5", weight="315", weight_unit="lbs"),
            ],
        )

        workout = ingest_to_workout(parsed)

        load = workout.blocks[0].exercises[0].load
        assert load is not None
        assert load.value == 315
        assert load.unit == "lb"

    def test_kg_weight(self):
        """Weight in kg is preserved."""
        parsed = ParsedWorkout(
            name="Metric",
            exercises=[
                ParsedExercise(raw_name="Squat", sets=5, reps="5", weight="140", weight_unit="kg"),
            ],
        )

        workout = ingest_to_workout(parsed)

        load = workout.blocks[0].exercises[0].load
        assert load.unit == "kg"

    def test_superset_grouping(self):
        """Exercises with same superset_group form a superset block."""
        parsed = ParsedWorkout(
            name="Supersets",
            exercises=[
                ParsedExercise(raw_name="Bicep Curl", sets=3, reps="12", superset_group="A"),
                ParsedExercise(raw_name="Tricep Extension", sets=3, reps="12", superset_group="A"),
                ParsedExercise(raw_name="Shoulder Press", sets=3, reps="10"),
            ],
        )

        workout = ingest_to_workout(parsed)

        # Should create 2 blocks: superset A and standalone
        assert workout.block_count == 2
        assert workout.blocks[0].type == BlockType.SUPERSET
        assert len(workout.blocks[0].exercises) == 2
        assert workout.blocks[1].type == BlockType.STRAIGHT

    def test_rest_seconds(self):
        """Rest seconds are preserved."""
        parsed = ParsedWorkout(
            name="With Rest",
            exercises=[
                ParsedExercise(raw_name="Squat", sets=3, reps="10", rest_seconds=90),
            ],
        )

        workout = ingest_to_workout(parsed)

        assert workout.blocks[0].exercises[0].rest_seconds == 90

    def test_tempo_preserved(self):
        """Tempo notation is preserved."""
        parsed = ParsedWorkout(
            name="Tempo",
            exercises=[
                ParsedExercise(raw_name="Squat", sets=3, reps="10", tempo="3010"),
            ],
        )

        workout = ingest_to_workout(parsed)

        assert workout.blocks[0].exercises[0].tempo == "3010"

    def test_notes_preserved(self):
        """Notes are preserved."""
        parsed = ParsedWorkout(
            name="Notes",
            exercises=[
                ParsedExercise(raw_name="Squat", sets=3, reps="10", notes="Go deep"),
            ],
        )

        workout = ingest_to_workout(parsed)

        assert workout.blocks[0].exercises[0].notes == "Go deep"

    def test_metadata_set_to_ai(self):
        """Ingest format should have AI source."""
        parsed = ParsedWorkout(
            name="AI Workout",
            exercises=[ParsedExercise(raw_name="Squat", sets=3, reps="10")],
        )

        workout = ingest_to_workout(parsed)

        assert WorkoutSource.AI in workout.metadata.sources


# =============================================================================
# blocks_to_workout tests
# =============================================================================


@pytest.mark.unit
class TestBlocksToWorkout:
    """Tests for blocks_to_workout converter."""

    def test_basic_blocks(self):
        """Convert basic blocks format."""
        blocks_json = {
            "title": "Full Body",
            "blocks": [
                {
                    "exercises": [
                        {"name": "Squat", "sets": 3, "reps": 10},
                        {"name": "Bench Press", "sets": 3, "reps": 8},
                    ]
                }
            ],
        }

        workout = blocks_to_workout(blocks_json)

        assert workout.title == "Full Body"
        assert workout.total_exercises == 2

    def test_supersets(self):
        """Convert blocks with supersets."""
        blocks_json = {
            "title": "Superset Workout",
            "blocks": [
                {
                    "supersets": [
                        {
                            "exercises": [
                                {"name": "Bicep Curl", "reps": 12},
                                {"name": "Tricep Extension", "reps": 12},
                            ]
                        }
                    ]
                }
            ],
        }

        workout = blocks_to_workout(blocks_json)

        assert workout.blocks[0].type == BlockType.SUPERSET
        assert len(workout.blocks[0].exercises) == 2

    def test_structure_rounds(self):
        """Parse structure for rounds."""
        blocks_json = {
            "title": "Circuit",
            "blocks": [
                {
                    "structure": "3 rounds",
                    "exercises": [{"name": "Burpee", "reps": 10}],
                }
            ],
        }

        workout = blocks_to_workout(blocks_json)

        assert workout.blocks[0].rounds == 3

    def test_structure_number_only(self):
        """Parse structure as just a number."""
        blocks_json = {
            "title": "Circuit",
            "blocks": [
                {
                    "structure": "4",
                    "exercises": [{"name": "Burpee", "reps": 10}],
                }
            ],
        }

        workout = blocks_to_workout(blocks_json)

        assert workout.blocks[0].rounds == 4

    def test_duration_sec(self):
        """Convert duration_sec field."""
        blocks_json = {
            "title": "Timed",
            "blocks": [
                {
                    "exercises": [{"name": "Plank", "duration_sec": 60}],
                }
            ],
        }

        workout = blocks_to_workout(blocks_json)

        assert workout.blocks[0].exercises[0].duration_seconds == 60

    def test_rest_sec_field(self):
        """Convert rest_sec to rest_seconds."""
        blocks_json = {
            "title": "Rest",
            "blocks": [
                {
                    "exercises": [{"name": "Squat", "reps": 10, "rest_sec": 90}],
                }
            ],
        }

        workout = blocks_to_workout(blocks_json)

        assert workout.blocks[0].exercises[0].rest_seconds == 90

    def test_weight_and_unit(self):
        """Convert weight and weight_unit to Load."""
        blocks_json = {
            "title": "Heavy",
            "blocks": [
                {
                    "exercises": [
                        {"name": "Squat", "reps": 5, "weight": 225, "weight_unit": "lbs"}
                    ],
                }
            ],
        }

        workout = blocks_to_workout(blocks_json)

        load = workout.blocks[0].exercises[0].load
        assert load.value == 225
        assert load.unit == "lb"

    def test_canonical_name_preserved(self):
        """Canonical name is preserved."""
        blocks_json = {
            "title": "Mapped",
            "blocks": [
                {
                    "exercises": [
                        {"name": "Squat", "canonical_name": "Barbell Back Squat", "reps": 5}
                    ],
                }
            ],
        }

        workout = blocks_to_workout(blocks_json)

        assert workout.blocks[0].exercises[0].canonical_name == "Barbell Back Squat"

    def test_distance_reps_as_string(self):
        """Distance format reps preserved as string."""
        blocks_json = {
            "title": "Running",
            "blocks": [
                {
                    "exercises": [{"name": "Run", "reps": "500m"}],
                }
            ],
        }

        workout = blocks_to_workout(blocks_json)

        assert workout.blocks[0].exercises[0].reps == "500m"

    def test_block_label(self):
        """Block label is preserved."""
        blocks_json = {
            "title": "Structured",
            "blocks": [
                {
                    "label": "Warm-up",
                    "exercises": [{"name": "Jumping Jacks", "reps": 30}],
                }
            ],
        }

        workout = blocks_to_workout(blocks_json)

        assert workout.blocks[0].label == "Warm-up"

    def test_rest_between_rounds(self):
        """Rest between rounds is captured."""
        blocks_json = {
            "title": "Circuit",
            "blocks": [
                {
                    "structure": "3 rounds",
                    "rest_between_rounds_sec": 120,
                    "exercises": [{"name": "Burpee", "reps": 10}],
                }
            ],
        }

        workout = blocks_to_workout(blocks_json)

        assert workout.blocks[0].rest_between_seconds == 120

    def test_metadata_from_blocks(self):
        """Metadata is parsed from blocks format."""
        blocks_json = {
            "title": "YouTube Import",
            "metadata": {
                "sources": ["youtube"],
                "platform": "garmin",
                "source_url": "https://youtube.com/watch?v=abc",
            },
            "blocks": [{"exercises": [{"name": "Squat", "reps": 10}]}],
        }

        workout = blocks_to_workout(blocks_json)

        assert WorkoutSource.YOUTUBE in workout.metadata.sources
        assert workout.metadata.platform == "garmin"
        assert workout.metadata.source_url == "https://youtube.com/watch?v=abc"

    def test_empty_blocks_raises(self):
        """Empty blocks raises ValueError."""
        blocks_json = {
            "title": "Empty",
            "blocks": [],
        }

        with pytest.raises(ValueError, match="at least one block"):
            blocks_to_workout(blocks_json)

    def test_workout_id_preserved(self):
        """Workout ID is preserved if present."""
        blocks_json = {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "title": "Existing",
            "blocks": [{"exercises": [{"name": "Squat", "reps": 10}]}],
        }

        workout = blocks_to_workout(blocks_json)

        assert workout.id == "123e4567-e89b-12d3-a456-426614174000"

    def test_tags_preserved(self):
        """Tags are preserved."""
        blocks_json = {
            "title": "Tagged",
            "tags": ["strength", "full-body"],
            "blocks": [{"exercises": [{"name": "Squat", "reps": 10}]}],
        }

        workout = blocks_to_workout(blocks_json)

        assert "strength" in workout.tags
        assert "full-body" in workout.tags


# =============================================================================
# db_row_to_workout tests
# =============================================================================


@pytest.mark.unit
class TestDbRowToWorkout:
    """Tests for db_row_to_workout converter."""

    def test_basic_row(self):
        """Convert basic database row."""
        row = {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "title": "Test Workout",
            "workout_data": {
                "title": "Test Workout",
                "blocks": [{"exercises": [{"name": "Squat", "reps": 10}]}],
            },
            "sources": ["ai"],
            "device": "garmin",
        }

        workout = db_row_to_workout(row)

        assert workout.id == "123e4567-e89b-12d3-a456-426614174000"
        assert workout.title == "Test Workout"
        assert workout.total_exercises == 1

    def test_sources_parsed(self):
        """Sources are parsed to WorkoutSource enum."""
        row = {
            "workout_data": {
                "title": "Multi-source",
                "blocks": [{"exercises": [{"name": "Squat", "reps": 10}]}],
            },
            "sources": ["ai", "youtube"],
        }

        workout = db_row_to_workout(row)

        assert WorkoutSource.AI in workout.metadata.sources
        assert WorkoutSource.YOUTUBE in workout.metadata.sources

    def test_timestamps_parsed(self):
        """Timestamps are parsed to datetime."""
        row = {
            "workout_data": {
                "title": "Timestamped",
                "blocks": [{"exercises": [{"name": "Squat", "reps": 10}]}],
            },
            "created_at": "2025-01-15T10:00:00Z",
            "updated_at": "2025-01-15T12:00:00+00:00",
        }

        workout = db_row_to_workout(row)

        assert workout.metadata.created_at is not None
        assert workout.metadata.updated_at is not None

    def test_export_tracking(self):
        """Export tracking fields are preserved."""
        row = {
            "workout_data": {
                "title": "Exported",
                "blocks": [{"exercises": [{"name": "Squat", "reps": 10}]}],
            },
            "is_exported": True,
            "exported_at": "2025-01-15T12:00:00Z",
            "exported_to_device": "Garmin Fenix 7",
        }

        workout = db_row_to_workout(row)

        assert workout.metadata.is_exported is True
        assert workout.metadata.exported_at is not None
        assert workout.metadata.exported_to_device == "Garmin Fenix 7"

    def test_favorite_tracking(self):
        """Favorite tracking is preserved."""
        row = {
            "workout_data": {
                "title": "Favorite",
                "blocks": [{"exercises": [{"name": "Squat", "reps": 10}]}],
            },
            "is_favorite": True,
        }

        workout = db_row_to_workout(row)

        assert workout.is_favorite is True

    def test_usage_tracking(self):
        """Usage tracking is preserved."""
        row = {
            "workout_data": {
                "title": "Used",
                "blocks": [{"exercises": [{"name": "Squat", "reps": 10}]}],
            },
            "times_completed": 5,
            "last_used_at": "2025-01-14T08:00:00Z",
        }

        workout = db_row_to_workout(row)

        assert workout.times_completed == 5
        assert workout.last_used_at is not None

    def test_tags_from_row(self):
        """Tags from row take precedence."""
        row = {
            "workout_data": {
                "title": "Tagged",
                "tags": ["old-tag"],
                "blocks": [{"exercises": [{"name": "Squat", "reps": 10}]}],
            },
            "tags": ["new-tag", "strength"],
        }

        workout = db_row_to_workout(row)

        assert "new-tag" in workout.tags
        assert "strength" in workout.tags

    def test_ios_companion_sync(self):
        """iOS companion sync timestamp is captured."""
        row = {
            "workout_data": {
                "title": "Synced",
                "blocks": [{"exercises": [{"name": "Squat", "reps": 10}]}],
            },
            "ios_companion_synced_at": "2025-01-15T10:00:00Z",
        }

        workout = db_row_to_workout(row)

        assert workout.metadata.ios_companion_synced_at is not None

    def test_missing_workout_data_raises(self):
        """Missing workout_data raises ValueError."""
        row = {
            "id": "123",
            "title": "No Data",
        }

        with pytest.raises(ValueError, match="missing workout_data"):
            db_row_to_workout(row)

    def test_title_override(self):
        """Row title overrides workout_data title."""
        row = {
            "title": "Row Title",
            "workout_data": {
                "title": "Data Title",
                "blocks": [{"exercises": [{"name": "Squat", "reps": 10}]}],
            },
        }

        workout = db_row_to_workout(row)

        assert workout.title == "Row Title"


# =============================================================================
# workout_to_db_row tests
# =============================================================================


@pytest.mark.unit
class TestWorkoutToDbRow:
    """Tests for workout_to_db_row converter."""

    def test_basic_workout_to_row(self):
        """Convert basic workout to database row."""
        workout = Workout(
            title="Test Workout",
            blocks=[Block(exercises=[Exercise(name="Squat", sets=3, reps=10)])],
        )

        row = workout_to_db_row(workout, profile_id="user-123", device="garmin")

        assert row["profile_id"] == "user-123"
        assert row["title"] == "Test Workout"
        assert row["device"] == "garmin"
        assert "workout_data" in row

    def test_workout_data_structure(self):
        """Workout data is serialized to blocks format."""
        workout = Workout(
            title="Structured",
            blocks=[
                Block(
                    label="Main",
                    exercises=[Exercise(name="Squat", sets=3, reps=10)],
                )
            ],
        )

        row = workout_to_db_row(workout, profile_id="user-123")

        workout_data = row["workout_data"]
        assert workout_data["title"] == "Structured"
        assert len(workout_data["blocks"]) == 1
        assert workout_data["blocks"][0]["label"] == "Main"

    def test_sources_serialized(self):
        """Sources are serialized to string array."""
        workout = Workout(
            title="AI Workout",
            blocks=[Block(exercises=[Exercise(name="Squat", reps=10)])],
            metadata=WorkoutMetadata(sources=[WorkoutSource.AI, WorkoutSource.YOUTUBE]),
        )

        row = workout_to_db_row(workout, profile_id="user-123")

        assert "ai" in row["sources"]
        assert "youtube" in row["sources"]

    def test_workout_id_included(self):
        """Workout ID is included if present."""
        workout = Workout(
            id="123e4567-e89b-12d3-a456-426614174000",
            title="Existing",
            blocks=[Block(exercises=[Exercise(name="Squat", reps=10)])],
        )

        row = workout_to_db_row(workout, profile_id="user-123")

        assert row["id"] == "123e4567-e89b-12d3-a456-426614174000"

    def test_description_included(self):
        """Description is included if present."""
        workout = Workout(
            title="Described",
            description="A great workout",
            blocks=[Block(exercises=[Exercise(name="Squat", reps=10)])],
        )

        row = workout_to_db_row(workout, profile_id="user-123")

        assert row["description"] == "A great workout"

    def test_tags_included(self):
        """Tags are included."""
        workout = Workout(
            title="Tagged",
            tags=["strength", "legs"],
            blocks=[Block(exercises=[Exercise(name="Squat", reps=10)])],
        )

        row = workout_to_db_row(workout, profile_id="user-123")

        assert row["tags"] == ["strength", "legs"]

    def test_export_tracking(self):
        """Export tracking fields are included."""
        exported_at = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        workout = Workout(
            title="Exported",
            blocks=[Block(exercises=[Exercise(name="Squat", reps=10)])],
            metadata=WorkoutMetadata(
                is_exported=True,
                exported_at=exported_at,
                exported_to_device="Garmin Fenix 7",
            ),
        )

        row = workout_to_db_row(workout, profile_id="user-123")

        assert row["is_exported"] is True
        assert "2025-01-15" in row["exported_at"]
        assert row["exported_to_device"] == "Garmin Fenix 7"

    def test_favorite_tracking(self):
        """Favorite flag is included."""
        workout = Workout(
            title="Favorite",
            blocks=[Block(exercises=[Exercise(name="Squat", reps=10)])],
            is_favorite=True,
        )

        row = workout_to_db_row(workout, profile_id="user-123")

        assert row["is_favorite"] is True

    def test_usage_tracking(self):
        """Usage tracking is included."""
        last_used = datetime(2025, 1, 14, 8, 0, 0, tzinfo=timezone.utc)
        workout = Workout(
            title="Used",
            blocks=[Block(exercises=[Exercise(name="Squat", reps=10)])],
            times_completed=5,
            last_used_at=last_used,
        )

        row = workout_to_db_row(workout, profile_id="user-123")

        assert row["times_completed"] == 5
        assert "2025-01-14" in row["last_used_at"]

    def test_load_serialization(self):
        """Load is serialized to weight/weight_unit."""
        workout = Workout(
            title="Heavy",
            blocks=[
                Block(
                    exercises=[
                        Exercise(name="Squat", sets=5, reps=5, load=Load(value=315, unit="lb"))
                    ]
                )
            ],
        )

        row = workout_to_db_row(workout, profile_id="user-123")

        ex_data = row["workout_data"]["blocks"][0]["exercises"][0]
        assert ex_data["weight"] == 315
        assert ex_data["weight_unit"] == "lb"

    def test_superset_serialization(self):
        """Supersets are serialized to supersets array."""
        workout = Workout(
            title="Superset",
            blocks=[
                Block(
                    type=BlockType.SUPERSET,
                    exercises=[
                        Exercise(name="Curl", reps=12),
                        Exercise(name="Extension", reps=12),
                    ],
                )
            ],
        )

        row = workout_to_db_row(workout, profile_id="user-123")

        block_data = row["workout_data"]["blocks"][0]
        assert block_data["structure"] == "superset"
        assert len(block_data["exercises"]) == 2

    def test_rounds_serialization(self):
        """Rounds > 1 are serialized to structure."""
        workout = Workout(
            title="Circuit",
            blocks=[
                Block(
                    rounds=4,
                    exercises=[Exercise(name="Burpee", reps=10)],
                )
            ],
        )

        row = workout_to_db_row(workout, profile_id="user-123")

        block_data = row["workout_data"]["blocks"][0]
        assert block_data.get("rounds") == 4

    def test_duration_serialization(self):
        """Duration is serialized to duration_sec."""
        workout = Workout(
            title="Timed",
            blocks=[
                Block(
                    exercises=[Exercise(name="Plank", duration_seconds=60)],
                )
            ],
        )

        row = workout_to_db_row(workout, profile_id="user-123")

        ex_data = row["workout_data"]["blocks"][0]["exercises"][0]
        assert ex_data["duration_sec"] == 60


# =============================================================================
# Round-trip tests
# =============================================================================


@pytest.mark.unit
class TestRoundTrip:
    """Test round-trip conversions preserve data."""

    def test_blocks_roundtrip(self):
        """blocks_to_workout -> workout_to_db_row preserves data."""
        original = {
            "title": "Round Trip",
            "blocks": [
                {
                    "label": "Main",
                    "structure": "3 rounds",
                    "exercises": [
                        {"name": "Squat", "sets": 3, "reps": 10, "weight": 225, "weight_unit": "lbs"},
                    ],
                }
            ],
            "tags": ["strength"],
            "metadata": {"sources": ["ai"], "platform": "garmin"},
        }

        workout = blocks_to_workout(original)
        row = workout_to_db_row(workout, profile_id="user-123", device="garmin")
        reconstructed = db_row_to_workout(row)

        assert reconstructed.title == original["title"]
        assert reconstructed.tags == ["strength"]
        assert reconstructed.blocks[0].rounds == 3

    def test_db_roundtrip(self):
        """db_row_to_workout -> workout_to_db_row preserves data."""
        original_row = {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "title": "Database Workout",
            "workout_data": {
                "title": "Database Workout",
                "blocks": [
                    {
                        "exercises": [
                            {"name": "Deadlift", "sets": 5, "reps": 5, "weight": 405, "weight_unit": "lbs"}
                        ]
                    }
                ],
            },
            "sources": ["manual"],
            "device": "apple",
            "is_favorite": True,
            "times_completed": 10,
            "tags": ["powerlifting"],
        }

        workout = db_row_to_workout(original_row)
        new_row = workout_to_db_row(workout, profile_id="user-123", device="apple")

        assert new_row["id"] == original_row["id"]
        assert new_row["title"] == original_row["title"]
        assert new_row["is_favorite"] == original_row["is_favorite"]
        assert new_row["times_completed"] == original_row["times_completed"]
        assert new_row["tags"] == original_row["tags"]

    def test_superset_roundtrip_preserves_block_type(self):
        """Superset block type survives write → read → write round-trip."""
        workout = Workout(
            title="Superset Round Trip",
            blocks=[
                Block(
                    type=BlockType.SUPERSET,
                    rounds=4,
                    exercises=[
                        Exercise(name="Pull-ups", reps=8),
                        Exercise(name="Z Press", reps=8),
                    ],
                    rest_between_seconds=60,
                )
            ],
        )

        # Write to DB format
        row = workout_to_db_row(workout, profile_id="user-123")
        # Read back from DB format
        reconstructed = db_row_to_workout(row)

        assert reconstructed.blocks[0].type == BlockType.SUPERSET
        assert reconstructed.blocks[0].rounds == 4
        assert len(reconstructed.blocks[0].exercises) == 2
        assert reconstructed.blocks[0].rest_between_seconds == 60

    def test_superset_db_to_workoutkit_pipeline(self):
        """Superset block type flows through DB serialization to WorkoutKit."""
        workout = Workout(
            title="Superset Pipeline",
            blocks=[
                Block(
                    type=BlockType.SUPERSET,
                    rounds=4,
                    exercises=[
                        Exercise(name="Pull-ups", reps=8),
                        Exercise(name="Z Press", reps=8),
                    ],
                    rest_between_seconds=60,
                )
            ],
        )

        # Serialize to DB format (what gets stored)
        row = workout_to_db_row(workout, profile_id="user-123")
        blocks_json = row["workout_data"]

        # Pass through to WorkoutKit (what iOS receives)
        wk_dto = to_workoutkit(blocks_json)

        # Should produce a RepeatInterval grouping the exercises
        assert len(wk_dto.intervals) == 1
        repeat = wk_dto.intervals[0]
        assert repeat.kind == "repeat"
        assert repeat.reps == 4
        # Inside: two exercise steps + rest
        exercise_steps = [s for s in repeat.intervals if s.kind == "reps"]
        rest_steps = [s for s in repeat.intervals if s.kind == "rest"]
        assert len(exercise_steps) == 2
        assert len(rest_steps) == 1
        assert rest_steps[0].seconds == 60

    def test_circuit_db_to_workoutkit_pipeline(self):
        """Circuit block type flows through DB serialization to WorkoutKit."""
        workout = Workout(
            title="Circuit Pipeline",
            blocks=[
                Block(
                    type=BlockType.CIRCUIT,
                    rounds=3,
                    exercises=[
                        Exercise(name="Burpees", reps=10),
                        Exercise(name="Jump Squats", reps=15),
                        Exercise(name="Push-ups", reps=20),
                    ],
                )
            ],
        )

        row = workout_to_db_row(workout, profile_id="user-123")
        blocks_json = row["workout_data"]
        wk_dto = to_workoutkit(blocks_json)

        assert len(wk_dto.intervals) == 1
        repeat = wk_dto.intervals[0]
        assert repeat.kind == "repeat"
        assert repeat.reps == 3
        exercise_steps = [s for s in repeat.intervals if s.kind == "reps"]
        assert len(exercise_steps) == 3

    def test_legacy_superset_format_still_works(self):
        """Old DB format with supersets[] array still produces correct domain model."""
        legacy_blocks_json = {
            "title": "Legacy Superset",
            "blocks": [
                {
                    "type": "superset",
                    "structure": "4 rounds",
                    "supersets": [
                        {
                            "exercises": [
                                {"name": "Curl", "reps": 12},
                                {"name": "Extension", "reps": 12},
                            ]
                        }
                    ],
                }
            ],
        }

        workout = blocks_to_workout(legacy_blocks_json)

        assert workout.blocks[0].type == BlockType.SUPERSET
        assert workout.blocks[0].rounds == 4
        assert len(workout.blocks[0].exercises) == 2

    def test_timed_round_db_to_workoutkit_pipeline(self):
        """Timed round block type flows through DB serialization to WorkoutKit."""
        workout = Workout(
            title="EMOM Pipeline",
            blocks=[
                Block(
                    type=BlockType.TIMED_ROUND,
                    rounds=5,
                    exercises=[
                        Exercise(name="Burpees", reps=10),
                        Exercise(name="Box Jumps", reps=8),
                    ],
                )
            ],
        )

        row = workout_to_db_row(workout, profile_id="user-123")
        blocks_json = row["workout_data"]

        # Verify serialization uses abstract format
        block_data = blocks_json["blocks"][0]
        assert block_data["structure"] == "timed_round"
        assert block_data["rounds"] == 5
        assert "exercises" in block_data

        # Pass through to WorkoutKit
        wk_dto = to_workoutkit(blocks_json)

        assert len(wk_dto.intervals) == 1
        repeat = wk_dto.intervals[0]
        assert repeat.kind == "repeat"
        assert repeat.reps == 5
        exercise_steps = [s for s in repeat.intervals if s.kind == "reps"]
        assert len(exercise_steps) == 2

    def test_legacy_superset_to_workoutkit_pipeline(self):
        """Old DB format with supersets[] array still produces correct WorkoutKit output."""
        legacy_blocks_json = {
            "title": "Legacy Superset WK",
            "blocks": [
                {
                    "type": "superset",
                    "structure": "4 rounds",
                    "supersets": [
                        {
                            "exercises": [
                                {"name": "Curl", "reps": 12},
                                {"name": "Extension", "reps": 12},
                            ]
                        }
                    ],
                }
            ],
        }

        wk_dto = to_workoutkit(legacy_blocks_json)

        # Legacy supersets[] path should still produce grouped intervals
        assert len(wk_dto.intervals) >= 1
        # Exercises should be present (via the legacy supersets[] processing)
        all_steps = []
        for interval in wk_dto.intervals:
            if hasattr(interval, "intervals"):
                all_steps.extend(interval.intervals)
            else:
                all_steps.append(interval)
        reps_steps = [s for s in all_steps if s.kind == "reps"]
        assert len(reps_steps) == 2
