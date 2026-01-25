"""
Contract test utilities.

Part of AMA-461: Create program-api service scaffold

Contract tests validate API response shapes and OpenAPI schema compliance.
"""

from typing import Any, Dict, List, Optional, Type, Union


def assert_response_shape(
    response_data: Any,
    expected_fields: Dict[str, Union[Type, tuple]],
    *,
    allow_extra: bool = True,
    path: str = "",
) -> None:
    """
    Assert that response data matches expected field types.

    Args:
        response_data: The response data to validate
        expected_fields: Dict mapping field names to expected types
        allow_extra: Whether to allow fields not in expected_fields
        path: Current path for error messages (used in recursion)

    Raises:
        AssertionError: If response doesn't match expected shape

    Example:
        assert_response_shape(
            response.json(),
            {
                "id": str,
                "name": str,
                "count": int,
                "items": list,
            }
        )
    """
    if not isinstance(response_data, dict):
        raise AssertionError(
            f"Expected dict at {path or 'root'}, got {type(response_data).__name__}"
        )

    # Check required fields are present
    for field, expected_type in expected_fields.items():
        field_path = f"{path}.{field}" if path else field
        if field not in response_data:
            raise AssertionError(f"Missing required field: {field_path}")

        value = response_data[field]

        # Handle None values
        if value is None:
            if expected_type is type(None) or (
                isinstance(expected_type, tuple) and type(None) in expected_type
            ):
                continue
            raise AssertionError(
                f"Field {field_path} is None but expected {expected_type}"
            )

        # Check type
        if isinstance(expected_type, tuple):
            if not isinstance(value, expected_type):
                raise AssertionError(
                    f"Field {field_path}: expected one of {expected_type}, "
                    f"got {type(value).__name__}"
                )
        else:
            if not isinstance(value, expected_type):
                raise AssertionError(
                    f"Field {field_path}: expected {expected_type.__name__}, "
                    f"got {type(value).__name__}"
                )

    # Check for unexpected fields
    if not allow_extra:
        extra_fields = set(response_data.keys()) - set(expected_fields.keys())
        if extra_fields:
            raise AssertionError(f"Unexpected fields at {path or 'root'}: {extra_fields}")


def assert_error_response(
    response_data: Any,
    *,
    expected_detail: Optional[str] = None,
) -> None:
    """
    Assert that response is a valid error response.

    Args:
        response_data: The response data to validate
        expected_detail: Optional expected detail message

    Raises:
        AssertionError: If response doesn't match error shape
    """
    assert_response_shape(response_data, {"detail": str})
    if expected_detail is not None:
        assert response_data["detail"] == expected_detail, (
            f"Expected detail '{expected_detail}', got '{response_data['detail']}'"
        )


def assert_list_response(
    response_data: Any,
    item_shape: Optional[Dict[str, Union[Type, tuple]]] = None,
) -> None:
    """
    Assert that response is a list with optional item shape validation.

    Args:
        response_data: The response data to validate
        item_shape: Optional dict of expected fields for each item

    Raises:
        AssertionError: If response is not a list or items don't match shape
    """
    if not isinstance(response_data, list):
        raise AssertionError(f"Expected list, got {type(response_data).__name__}")

    if item_shape and response_data:
        for i, item in enumerate(response_data):
            assert_response_shape(item, item_shape, path=f"[{i}]")
