"""
Application-layer exceptions.

Part of AMA-489: Add Transaction Handling for Program Creation

These exceptions are used across application and infrastructure layers.
"""


class ProgramCreationError(Exception):
    """Error during atomic program creation.

    Raised when the atomic creation of a program with its weeks
    and workouts fails. This could be due to database errors,
    constraint violations, or RPC failures.
    """

    pass
