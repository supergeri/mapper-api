"""
Input sanitization utilities.

Part of AMA-491: Sanitize user limitations input

Shared sanitization functions to prevent prompt injection attacks.
This module has no dependencies on models or services to avoid circular imports.
"""

import re

from core.constants import MAX_LIMITATION_LENGTH


def sanitize_user_input(value: str, max_length: int = MAX_LIMITATION_LENGTH) -> str:
    """
    Sanitize user input by removing control characters and limiting length.

    This function is designed to prevent prompt injection attacks by:
    - Removing newlines, carriage returns, tabs, and control characters
    - Collapsing multiple spaces into one
    - Stripping leading/trailing whitespace
    - Truncating to a maximum length

    Args:
        value: Raw user-provided string
        max_length: Maximum allowed length (default: MAX_LIMITATION_LENGTH)

    Returns:
        Sanitized string safe for prompt inclusion
    """
    # Remove newlines, carriage returns, tabs, and other control characters
    sanitized = re.sub(r"[\n\r\t\x00-\x1f\x7f-\x9f]", " ", value)
    # Collapse multiple spaces into one
    sanitized = re.sub(r" +", " ", sanitized)
    # Strip leading/trailing whitespace
    sanitized = sanitized.strip()
    # Limit length
    return sanitized[:max_length]
