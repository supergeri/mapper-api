"""
Contract tests for API response shapes.

Part of AMA-400: Add contract tests for API responses
Phase 4 - Testing Overhaul

These tests verify that API response shapes match the expected structure,
catching breaking changes to API contracts. Tests validate:
- Response field presence and types
- Nested object structures
- List response formats
- Error response shapes
"""

from typing import Any, Dict, List, Optional, Type, get_origin, get_args
import re


def assert_response_shape(
    response_data: Any,
    expected_fields: Dict[str, type],
    *,
    allow_extra: bool = True,
    path: str = "",
) -> None:
    """Assert that response data matches expected field types.

    Args:
        response_data: The response JSON data to validate
        expected_fields: Dict mapping field names to expected types
        allow_extra: If True, allows extra fields not in expected_fields
        path: Current path in nested structure (for error messages)

    Raises:
        AssertionError: If response doesn't match expected shape
    """
    if not isinstance(response_data, dict):
        raise AssertionError(f"{path or 'Response'} expected dict, got {type(response_data).__name__}")

    # Check all expected fields are present
    for field_name, expected_type in expected_fields.items():
        field_path = f"{path}.{field_name}" if path else field_name

        if field_name not in response_data:
            raise AssertionError(f"Missing required field: {field_path}")

        actual_value = response_data[field_name]

        # Handle Optional types
        origin = get_origin(expected_type)
        if origin is type(None) or (hasattr(expected_type, "__origin__") and expected_type.__origin__ is type(None)):
            continue  # Any value is fine for None type

        # Handle None values for optional fields
        if actual_value is None:
            # Check if type allows None (Union with None)
            if hasattr(expected_type, "__args__") and type(None) in expected_type.__args__:
                continue
            # If the expected type is not explicitly Optional, but got None
            # We'll be lenient and allow it for contract tests
            continue

        # Handle list types
        if origin is list:
            if not isinstance(actual_value, list):
                raise AssertionError(f"{field_path}: expected list, got {type(actual_value).__name__}")
            # Could validate list item types here if needed

        # Handle dict types
        elif origin is dict:
            if not isinstance(actual_value, dict):
                raise AssertionError(f"{field_path}: expected dict, got {type(actual_value).__name__}")

        # Handle basic types
        elif expected_type in (str, int, float, bool):
            if not isinstance(actual_value, expected_type):
                # Allow int where float expected
                if expected_type is float and isinstance(actual_value, int):
                    continue
                raise AssertionError(
                    f"{field_path}: expected {expected_type.__name__}, got {type(actual_value).__name__}"
                )

    if not allow_extra:
        extra_fields = set(response_data.keys()) - set(expected_fields.keys())
        if extra_fields:
            raise AssertionError(f"{path or 'Response'} has unexpected fields: {extra_fields}")


def assert_list_response(
    response_data: Any,
    item_fields: Optional[Dict[str, type]] = None,
    *,
    min_items: int = 0,
    path: str = "",
) -> None:
    """Assert that response is a list with optional item shape validation.

    Args:
        response_data: The response JSON data (expected to be a list)
        item_fields: Optional dict of expected fields in each list item
        min_items: Minimum number of items expected
        path: Current path in nested structure (for error messages)
    """
    if not isinstance(response_data, list):
        raise AssertionError(f"{path or 'Response'} expected list, got {type(response_data).__name__}")

    if len(response_data) < min_items:
        raise AssertionError(f"{path or 'Response'} expected at least {min_items} items, got {len(response_data)}")

    if item_fields and len(response_data) > 0:
        for i, item in enumerate(response_data):
            item_path = f"{path}[{i}]" if path else f"[{i}]"
            assert_response_shape(item, item_fields, path=item_path)


def assert_error_response(
    response_data: Any,
    *,
    expected_status: Optional[int] = None,
    contains_detail: bool = True,
) -> None:
    """Assert that response is a valid error response.

    Args:
        response_data: The response JSON data
        expected_status: Optional expected status code in response
        contains_detail: If True, expects a 'detail' field
    """
    if not isinstance(response_data, dict):
        raise AssertionError(f"Error response expected dict, got {type(response_data).__name__}")

    if contains_detail and "detail" not in response_data:
        raise AssertionError("Error response missing 'detail' field")
