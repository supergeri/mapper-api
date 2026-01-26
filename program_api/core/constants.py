"""
Shared constants.

Part of AMA-491: Sanitize user limitations input

This module has no dependencies on models or services to avoid circular imports.
"""

# Maximum length for a single user limitation string
MAX_LIMITATION_LENGTH = 100

# Maximum number of limitations allowed per request
MAX_LIMITATIONS_COUNT = 10
