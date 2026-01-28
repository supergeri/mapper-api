"""
PatchWorkout Use Case.

Part of AMA-433: PATCH /workouts/{id} endpoint implementation

Orchestrates workout patching with validation, handling JSON Patch-style
operations for chat-driven workout editing.

Workflow:
1. Fetch workout via repository
2. Validate patch operations (including length limits)
3. Apply patch operations to dict representation
4. Re-validate via domain model
5. Persist and clear embedding hash (single atomic update)
6. Log to audit trail (best-effort, non-blocking)
7. Return PatchWorkoutResult
"""

import copy
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from application.ports import WorkoutRepository
from domain.converters.blocks_to_workout import blocks_to_workout
from domain.models import Workout
from domain.models.patch_operation import (
    PatchOperation,
    parse_path,
    validate_path_structure,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Constants for Input Validation
# =============================================================================

MAX_TITLE_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 2000  # Must match domain/models/workout.py
MAX_NOTES_LENGTH = 2000  # Must match domain/models/workout.py
MAX_TAG_LENGTH = 100
MAX_TAGS_COUNT = 50
MAX_EXERCISE_NAME_LENGTH = 200
MAX_EXERCISE_NOTES_LENGTH = 1000


class PatchValidationError(Exception):
    """Raised when patch validation fails."""

    def __init__(self, message: str, errors: Optional[List[str]] = None):
        super().__init__(message)
        self.message = message
        self.errors = errors or []


@dataclass
class PatchWorkoutResult:
    """Result of the PatchWorkout use case execution."""

    success: bool
    workout: Optional[Dict[str, Any]] = None
    changes_applied: int = 0
    embedding_regeneration: str = "none"
    error: Optional[str] = None
    validation_errors: List[str] = field(default_factory=list)


class PatchWorkoutUseCase:
    """
    Use case for patching workouts with JSON Patch operations.

    Orchestrates the following workflow:
    1. Fetch workout by ID via repository
    2. Validate patch operations (structure and value constraints)
    3. Apply patches to workout data
    4. Re-validate via domain model
    5. Persist updated workout with cleared embedding hash
    6. Log to audit trail (best-effort)
    7. Return result

    Dependencies are injected via constructor for testability.

    Usage:
        >>> use_case = PatchWorkoutUseCase(workout_repo=repo)
        >>> result = use_case.execute(
        ...     workout_id="abc123",
        ...     user_id="user-123",
        ...     operations=[
        ...         PatchOperation(op="replace", path="/title", value="New Title"),
        ...     ],
        ... )
        >>> if result.success:
        ...     print(f"Applied {result.changes_applied} changes")
    """

    def __init__(self, workout_repo: WorkoutRepository) -> None:
        """
        Initialize the use case with required dependencies.

        Args:
            workout_repo: Repository for workout persistence operations
        """
        self._workout_repo = workout_repo

    def execute(
        self,
        workout_id: str,
        user_id: str,
        operations: List[PatchOperation],
    ) -> PatchWorkoutResult:
        """
        Execute the patch workout workflow.

        Args:
            workout_id: ID of the workout to patch
            user_id: User profile ID for authorization
            operations: List of patch operations to apply

        Returns:
            PatchWorkoutResult with success status and updated workout
        """
        try:
            # Step 1: Fetch workout via repository
            workout_row = self._workout_repo.get_workout_by_id(workout_id, user_id)
            if workout_row is None:
                return PatchWorkoutResult(
                    success=False,
                    error="Workout not found or not owned by user",
                )

            # Step 2: Validate all operations upfront
            validation_errors = self._validate_operations(operations, workout_row)
            if validation_errors:
                return PatchWorkoutResult(
                    success=False,
                    error="Patch operation validation failed",
                    validation_errors=validation_errors,
                )

            # Step 3: Apply patches to workout_data
            workout_data = copy.deepcopy(workout_row.get("workout_data", {}))

            # Also track top-level fields that might change
            title = workout_row.get("title") or workout_data.get("title")
            description = workout_row.get("description") or workout_data.get("description")
            tags = workout_row.get("tags") or workout_data.get("tags", [])

            changes_applied = 0
            for op in operations:
                try:
                    workout_data, title, description, tags, changed = self._apply_operation(
                        op, workout_data, title, description, tags
                    )
                    if changed:
                        changes_applied += 1
                    else:
                        # Log when operation doesn't result in change
                        logger.debug(
                            f"Operation {op.op} on {op.path} did not result in change "
                            f"(possibly non-existent index or no-op)"
                        )
                except Exception as e:
                    logger.warning(f"Failed to apply operation {op}: {e}")
                    return PatchWorkoutResult(
                        success=False,
                        error=f"Failed to apply operation: {str(e)}",
                        validation_errors=[str(e)],
                    )

            # Sync title/description/tags back into workout_data
            if title:
                workout_data["title"] = title
            if description:
                workout_data["description"] = description
            if tags is not None:
                workout_data["tags"] = tags

            # Step 4: Re-validate via domain model
            try:
                workout = blocks_to_workout(workout_data)
            except Exception as e:
                logger.warning(f"Workout validation failed after patch: {e}")
                return PatchWorkoutResult(
                    success=False,
                    error="Workout validation failed after applying patches",
                    validation_errors=[str(e)],
                )

            # Additional business validation
            biz_errors = self._validate_workout_business_rules(workout)
            if biz_errors:
                return PatchWorkoutResult(
                    success=False,
                    error="Business validation failed",
                    validation_errors=biz_errors,
                )

            # Step 5: Persist updated workout with cleared embedding hash (atomic)
            updated_row = self._workout_repo.update_workout_data(
                workout_id=workout_id,
                profile_id=user_id,
                workout_data=workout_data,
                title=title,
                description=description,
                tags=tags,
                clear_embedding=True,  # Clear embedding hash to trigger regeneration
            )

            if updated_row is None:
                return PatchWorkoutResult(
                    success=False,
                    error="Failed to persist workout update",
                )

            # Step 6: Log to audit trail (best-effort, non-blocking)
            self._log_audit_trail(
                workout_id=workout_id,
                user_id=user_id,
                operations=operations,
                changes_applied=changes_applied,
            )

            # Step 7: Return result
            return PatchWorkoutResult(
                success=True,
                workout=updated_row,
                changes_applied=changes_applied,
                embedding_regeneration="queued",
            )

        except PatchValidationError as e:
            logger.warning(f"Patch validation error: {e}")
            return PatchWorkoutResult(
                success=False,
                error=e.message,
                validation_errors=e.errors,
            )

        except Exception as e:
            logger.exception(f"PatchWorkout use case failed: {e}")
            return PatchWorkoutResult(
                success=False,
                error=str(e),
            )

    def _validate_operations(
        self, operations: List[PatchOperation], workout_row: Dict[str, Any]
    ) -> List[str]:
        """Validate all operations before applying."""
        errors = []
        workout_data = workout_row.get("workout_data", {})
        blocks = workout_data.get("blocks", [])

        for i, op in enumerate(operations):
            # Validate path structure
            path_error = validate_path_structure(op.path)
            if path_error:
                errors.append(f"Operation {i}: {path_error}")
                continue

            # Validate path exists for replace/remove operations
            segments = parse_path(op.path)

            if op.op in ("replace", "remove"):
                if not self._path_exists(segments, workout_data, blocks):
                    # For exercises shorthand, also check if it resolves
                    if segments[0] == "exercises" and len(blocks) > 0:
                        # This is OK - we'll apply to first block
                        pass
                    else:
                        errors.append(f"Operation {i}: Path does not exist: {op.path}")

            # Validate value for add/replace (including length constraints)
            if op.op in ("add", "replace"):
                value_error = self._validate_value(op, segments)
                if value_error:
                    errors.append(f"Operation {i}: {value_error}")

        return errors

    def _path_exists(
        self, segments: List[str], workout_data: Dict[str, Any], blocks: List[Dict]
    ) -> bool:
        """Check if a path exists in the workout data."""
        if not segments:
            return False

        root = segments[0]

        # Simple top-level paths
        if root in ("title", "name"):
            return "title" in workout_data or True  # title always "exists"
        if root == "description":
            return True
        if root == "notes":
            return True
        if root == "tags":
            if len(segments) == 1:
                return True
            if len(segments) == 2:
                tags = workout_data.get("tags", [])
                if segments[1] == "-":
                    return True
                try:
                    idx = int(segments[1])
                    return 0 <= idx < len(tags)
                except ValueError:
                    return False
            return False

        # Exercises shorthand (first block)
        if root == "exercises":
            if len(blocks) == 0:
                return False
            first_block = blocks[0]
            exercises = first_block.get("exercises", [])

            if len(segments) == 1:
                return True
            if segments[1] == "-":
                return True
            try:
                idx = int(segments[1])
                if idx < 0 or idx >= len(exercises):
                    return False
                if len(segments) == 2:
                    return True
                # Check exercise field
                return True  # Field validation happens elsewhere
            except ValueError:
                return False

        # Blocks path
        if root == "blocks":
            if len(segments) < 2:
                return False
            if segments[1] == "-":
                return True
            try:
                block_idx = int(segments[1])
                if block_idx < 0 or block_idx >= len(blocks):
                    return False
                if len(segments) == 2:
                    return True

                block = blocks[block_idx]

                if segments[2] == "exercises":
                    block_exercises = block.get("exercises", [])
                    if len(segments) == 3:
                        return True
                    if segments[3] == "-":
                        return True
                    try:
                        ex_idx = int(segments[3])
                        return 0 <= ex_idx < len(block_exercises)
                    except ValueError:
                        return False

                # Block field
                return True
            except ValueError:
                return False

        return False

    def _validate_value(self, op: PatchOperation, segments: List[str]) -> Optional[str]:
        """Validate value type and length for the target path."""
        root = segments[0]

        # Title validation
        if root in ("title", "name"):
            if not isinstance(op.value, str):
                return "Title must be a string"
            if not op.value.strip():
                return "Title cannot be empty"
            if len(op.value) > MAX_TITLE_LENGTH:
                return f"Title cannot exceed {MAX_TITLE_LENGTH} characters"

        # Description validation
        if root == "description":
            if op.value is not None and not isinstance(op.value, str):
                return "Description must be a string"
            if op.value and len(op.value) > MAX_DESCRIPTION_LENGTH:
                return f"Description cannot exceed {MAX_DESCRIPTION_LENGTH} characters"

        # Notes validation
        if root == "notes":
            if op.value is not None and not isinstance(op.value, str):
                return "Notes must be a string"
            if op.value and len(op.value) > MAX_NOTES_LENGTH:
                return f"Notes cannot exceed {MAX_NOTES_LENGTH} characters"

        # Tags validation
        if root == "tags":
            if len(segments) == 1:
                # Replacing entire tags array
                if not isinstance(op.value, list):
                    return "Tags must be an array"
                if len(op.value) > MAX_TAGS_COUNT:
                    return f"Cannot have more than {MAX_TAGS_COUNT} tags"
                for i, tag in enumerate(op.value):
                    if not isinstance(tag, str):
                        return f"Tag at index {i} must be a string"
                    if len(tag) > MAX_TAG_LENGTH:
                        return f"Tag at index {i} exceeds {MAX_TAG_LENGTH} characters"
            else:
                # Adding/replacing single tag
                if not isinstance(op.value, str):
                    return "Tag value must be a string"
                if len(op.value) > MAX_TAG_LENGTH:
                    return f"Tag cannot exceed {MAX_TAG_LENGTH} characters"

        # Exercise validation
        if root == "exercises" or (root == "blocks" and "exercises" in segments):
            # Check if we're setting an entire exercise
            if op.path.endswith("/-") or (len(segments) >= 2 and segments[-1].isdigit()):
                if isinstance(op.value, dict):
                    if "name" not in op.value or not op.value["name"]:
                        return "Exercise must have a name"
                    if len(op.value.get("name", "")) > MAX_EXERCISE_NAME_LENGTH:
                        return f"Exercise name cannot exceed {MAX_EXERCISE_NAME_LENGTH} characters"
                    if op.value.get("notes") and len(op.value["notes"]) > MAX_EXERCISE_NOTES_LENGTH:
                        return f"Exercise notes cannot exceed {MAX_EXERCISE_NOTES_LENGTH} characters"

            # Check if we're setting exercise name field directly
            if len(segments) >= 3 and segments[-1] == "name":
                if not isinstance(op.value, str):
                    return "Exercise name must be a string"
                if not op.value.strip():
                    return "Exercise name cannot be empty"
                if len(op.value) > MAX_EXERCISE_NAME_LENGTH:
                    return f"Exercise name cannot exceed {MAX_EXERCISE_NAME_LENGTH} characters"

            # Check if we're setting exercise notes field directly
            if len(segments) >= 3 and segments[-1] == "notes":
                if op.value and not isinstance(op.value, str):
                    return "Exercise notes must be a string"
                if op.value and len(op.value) > MAX_EXERCISE_NOTES_LENGTH:
                    return f"Exercise notes cannot exceed {MAX_EXERCISE_NOTES_LENGTH} characters"

        return None

    def _apply_operation(
        self,
        op: PatchOperation,
        workout_data: Dict[str, Any],
        title: Optional[str],
        description: Optional[str],
        tags: Optional[List[str]],
    ) -> tuple[Dict[str, Any], Optional[str], Optional[str], Optional[List[str]], bool]:
        """
        Apply a single patch operation.

        Returns:
            Tuple of (workout_data, title, description, tags, changed)
        """
        segments = parse_path(op.path)
        root = segments[0]
        changed = False

        # Handle title/name
        if root in ("title", "name"):
            if op.op == "replace":
                title = op.value
                workout_data["title"] = op.value
                changed = True
            elif op.op == "remove":
                # Cannot remove title
                raise ValueError("Cannot remove workout title")

        # Handle description
        elif root == "description":
            if op.op == "replace":
                description = op.value
                workout_data["description"] = op.value
                changed = True
            elif op.op == "remove":
                description = None
                workout_data.pop("description", None)
                changed = True

        # Handle notes
        elif root == "notes":
            if op.op == "replace":
                workout_data["notes"] = op.value
                changed = True
            elif op.op == "remove":
                workout_data.pop("notes", None)
                changed = True

        # Handle tags
        elif root == "tags":
            if len(segments) == 1:
                if op.op == "replace":
                    tags = op.value
                    workout_data["tags"] = op.value
                    changed = True
                elif op.op == "remove":
                    tags = []
                    workout_data["tags"] = []
                    changed = True
            else:
                current_tags = list(tags) if tags else []
                if segments[1] == "-":
                    if op.op == "add":
                        current_tags.append(op.value)
                        changed = True
                else:
                    try:
                        idx = int(segments[1])
                        if op.op == "replace":
                            if 0 <= idx < len(current_tags):
                                current_tags[idx] = op.value
                                changed = True
                        elif op.op == "remove":
                            if 0 <= idx < len(current_tags):
                                current_tags.pop(idx)
                                changed = True
                    except ValueError:
                        pass
                tags = current_tags
                workout_data["tags"] = current_tags

        # Handle exercises shorthand (first block)
        elif root == "exercises":
            blocks = workout_data.get("blocks", [])
            if not blocks:
                blocks = [{"exercises": []}]
                workout_data["blocks"] = blocks

            first_block = blocks[0]
            exercises = first_block.get("exercises", [])

            if segments[1] == "-":
                if op.op == "add":
                    exercises.append(op.value)
                    changed = True
            else:
                try:
                    ex_idx = int(segments[1])
                    if len(segments) == 2:
                        # Replace/remove entire exercise
                        if op.op == "replace":
                            if 0 <= ex_idx < len(exercises):
                                exercises[ex_idx] = op.value
                                changed = True
                        elif op.op == "remove":
                            if 0 <= ex_idx < len(exercises):
                                exercises.pop(ex_idx)
                                changed = True
                    else:
                        # Modify exercise field
                        field = segments[2]
                        if 0 <= ex_idx < len(exercises):
                            if op.op == "replace":
                                exercises[ex_idx][field] = op.value
                                changed = True
                            elif op.op == "remove":
                                exercises[ex_idx].pop(field, None)
                                changed = True
                except ValueError:
                    pass

            first_block["exercises"] = exercises

        # Handle blocks
        elif root == "blocks":
            blocks = workout_data.get("blocks", [])

            if segments[1] == "-":
                if op.op == "add":
                    blocks.append(op.value)
                    changed = True
            else:
                try:
                    block_idx = int(segments[1])
                    if len(segments) == 2:
                        # Replace/remove entire block
                        if op.op == "replace":
                            if 0 <= block_idx < len(blocks):
                                blocks[block_idx] = op.value
                                changed = True
                        elif op.op == "remove":
                            if 0 <= block_idx < len(blocks):
                                blocks.pop(block_idx)
                                changed = True
                    elif segments[2] == "exercises":
                        block = blocks[block_idx]
                        block_exercises = block.get("exercises", [])

                        if len(segments) == 3:
                            # Cannot replace entire exercises array
                            pass
                        elif segments[3] == "-":
                            if op.op == "add":
                                block_exercises.append(op.value)
                                changed = True
                        else:
                            ex_idx = int(segments[3])
                            if len(segments) == 4:
                                if op.op == "replace":
                                    if 0 <= ex_idx < len(block_exercises):
                                        block_exercises[ex_idx] = op.value
                                        changed = True
                                elif op.op == "remove":
                                    if 0 <= ex_idx < len(block_exercises):
                                        block_exercises.pop(ex_idx)
                                        changed = True
                            else:
                                # Exercise field
                                field = segments[4]
                                if 0 <= ex_idx < len(block_exercises):
                                    if op.op == "replace":
                                        block_exercises[ex_idx][field] = op.value
                                        changed = True
                                    elif op.op == "remove":
                                        block_exercises[ex_idx].pop(field, None)
                                        changed = True

                        block["exercises"] = block_exercises
                    else:
                        # Block field
                        field = segments[2]
                        if 0 <= block_idx < len(blocks):
                            if op.op == "replace":
                                blocks[block_idx][field] = op.value
                                changed = True
                            elif op.op == "remove":
                                blocks[block_idx].pop(field, None)
                                changed = True
                except (ValueError, IndexError):
                    pass

            workout_data["blocks"] = blocks

        return workout_data, title, description, tags, changed

    def _validate_workout_business_rules(self, workout: Workout) -> List[str]:
        """Validate business rules on the domain model."""
        errors: List[str] = []

        if not workout.title or not workout.title.strip():
            errors.append("Workout title is required")

        if not workout.blocks:
            errors.append("Workout must have at least one block")

        for i, block in enumerate(workout.blocks):
            if not block.exercises:
                errors.append(f"Block {i + 1} has no exercises")

        for block in workout.blocks:
            for ex in block.exercises:
                if not ex.name or not ex.name.strip():
                    errors.append("All exercises must have a name")
                    break

        if workout.total_exercises == 0:
            errors.append("Workout must contain at least one exercise")

        return errors

    def _log_audit_trail(
        self,
        workout_id: str,
        user_id: str,
        operations: List[PatchOperation],
        changes_applied: int,
    ) -> None:
        """
        Log patch operations to audit trail (best-effort).

        Note: This is a best-effort operation. If it fails, the patch
        operation still succeeds. Audit logging failures are logged
        but do not affect the main workflow.
        """
        try:
            operations_data = [
                {"op": op.op, "path": op.path, "value": op.value}
                for op in operations
            ]

            self._workout_repo.log_patch_audit(
                workout_id=workout_id,
                user_id=user_id,
                operations=operations_data,
                changes_applied=changes_applied,
            )

            logger.info(
                f"Logged {changes_applied} changes to audit trail for workout {workout_id}"
            )
        except Exception as e:
            # Don't fail the operation if audit logging fails
            logger.warning(f"Failed to log audit trail for {workout_id}: {e}")
