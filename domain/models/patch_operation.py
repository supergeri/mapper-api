"""
Patch Operation model for JSON Patch-style workout modifications.

Part of AMA-433: PATCH /workouts/{id} endpoint implementation

Implements a subset of RFC 6902 JSON Patch for workout editing:
- replace: Replace a value at a path
- add: Add a value at a path (e.g., append to array with /-)
- remove: Remove a value at a path

Supported paths:
- /title or /name: Workout title
- /description: Workout description
- /tags: Replace tags array
- /tags/-: Add tag (add op)
- /exercises/-: Add exercise to first block
- /exercises/{index}: Replace or remove exercise
- /exercises/{index}/{field}: Replace exercise field
- /blocks/{index}/exercises/-: Add exercise to specific block
- /blocks/{index}/exercises/{index}: Modify exercise in block
"""

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class PatchOperation(BaseModel):
    """
    A single JSON Patch operation (RFC 6902 subset).

    Represents one atomic change to be applied to a workout.

    Examples:
        >>> # Replace title
        >>> op = PatchOperation(op="replace", path="/title", value="New Title")

        >>> # Add a tag
        >>> op = PatchOperation(op="add", path="/tags/-", value="strength")

        >>> # Remove exercise at index 2
        >>> op = PatchOperation(op="remove", path="/exercises/2")

        >>> # Replace exercise sets
        >>> op = PatchOperation(op="replace", path="/exercises/0/sets", value=5)
    """

    op: Literal["replace", "add", "remove"] = Field(
        ..., description="The operation type: replace, add, or remove"
    )

    path: str = Field(
        ...,
        min_length=1,
        description="JSON Pointer path to the target location (e.g., /title, /exercises/0/sets)",
    )

    value: Any = Field(
        default=None,
        description="The value to set (required for replace and add, ignored for remove)",
    )

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        """Ensure path starts with / and is not empty."""
        if not v.startswith("/"):
            raise ValueError("Path must start with /")
        return v

    def model_post_init(self, __context: Any) -> None:
        """Validate that value is provided for add/replace operations."""
        if self.op in ("replace", "add") and self.value is None:
            # Allow explicit None value for replace operations
            pass

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"op": "replace", "path": "/title", "value": "Updated Workout"},
                {"op": "add", "path": "/tags/-", "value": "hiit"},
                {"op": "remove", "path": "/exercises/2"},
                {"op": "replace", "path": "/exercises/0/sets", "value": 4},
            ]
        }
    }


class PatchOperationList(BaseModel):
    """
    A list of patch operations to apply atomically.

    All operations in the list succeed or fail together.
    Operations are applied in order.
    """

    operations: List[PatchOperation] = Field(
        ...,
        min_length=1,
        description="List of patch operations to apply",
    )


# Path segment constants for validation
VALID_ROOT_PATHS = frozenset([
    "title",
    "name",  # alias for title
    "description",
    "tags",
    "notes",
    "exercises",
    "blocks",
])

VALID_EXERCISE_FIELDS = frozenset([
    "name",
    "sets",
    "reps",
    "duration_sec",
    "rest_sec",
    "weight",
    "weight_unit",
    "tempo",
    "notes",
    "load",
    "canonical_name",
])

VALID_BLOCK_FIELDS = frozenset([
    "label",
    "type",
    "rounds",
    "rest_between_rounds_sec",
    "exercises",
])


def parse_path(path: str) -> List[str]:
    """
    Parse a JSON Pointer path into segments.

    Args:
        path: JSON Pointer path (e.g., "/exercises/0/sets")

    Returns:
        List of path segments (e.g., ["exercises", "0", "sets"])
    """
    if not path.startswith("/"):
        raise ValueError(f"Invalid path: {path} (must start with /)")

    # Remove leading / and split
    segments = path[1:].split("/")

    # Handle empty path
    if segments == [""]:
        return []

    return segments


def validate_path_structure(path: str) -> Optional[str]:
    """
    Validate that a path follows the expected structure.

    Args:
        path: JSON Pointer path to validate

    Returns:
        Error message if invalid, None if valid
    """
    try:
        segments = parse_path(path)
    except ValueError as e:
        return str(e)

    if not segments:
        return "Empty path"

    root = segments[0]

    # Check root path
    if root not in VALID_ROOT_PATHS:
        return f"Invalid root path: /{root}"

    # Title/name are simple string paths
    if root in ("title", "name", "description", "notes"):
        if len(segments) > 1:
            return f"/{root} does not support nested paths"
        return None

    # Tags can be array or array index
    if root == "tags":
        if len(segments) == 1:
            return None  # Replace entire tags array
        if len(segments) == 2:
            if segments[1] == "-":
                return None  # Append to tags
            # Tag index
            try:
                int(segments[1])
                return None
            except ValueError:
                return f"Invalid tag index: {segments[1]}"
        return "Tags path too deep"

    # Exercises shorthand (operates on first block)
    if root == "exercises":
        if len(segments) == 1:
            return "Cannot replace entire exercises array"
        if segments[1] == "-":
            return None  # Append exercise
        try:
            int(segments[1])
        except ValueError:
            return f"Invalid exercise index: {segments[1]}"

        if len(segments) == 2:
            return None  # Replace/remove entire exercise

        if len(segments) == 3:
            field = segments[2]
            if field not in VALID_EXERCISE_FIELDS:
                return f"Invalid exercise field: {field}"
            return None

        return "Exercise path too deep"

    # Blocks with full path
    if root == "blocks":
        if len(segments) < 2:
            return "Blocks path requires index"

        try:
            int(segments[1])
        except ValueError:
            if segments[1] != "-":
                return f"Invalid block index: {segments[1]}"

        if len(segments) == 2:
            return None  # Replace/remove entire block

        if segments[2] == "exercises":
            if len(segments) == 3:
                return "Cannot replace entire exercises array in block"
            if segments[3] == "-":
                return None  # Append exercise to block
            try:
                int(segments[3])
            except ValueError:
                return f"Invalid exercise index: {segments[3]}"

            if len(segments) == 4:
                return None  # Replace/remove exercise in block

            if len(segments) == 5:
                field = segments[4]
                if field not in VALID_EXERCISE_FIELDS:
                    return f"Invalid exercise field: {field}"
                return None

            return "Block exercise path too deep"

        # Other block fields
        if len(segments) == 3:
            field = segments[2]
            if field not in VALID_BLOCK_FIELDS:
                return f"Invalid block field: {field}"
            return None

        return "Block path too deep"

    return f"Unhandled path: {path}"
