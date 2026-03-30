"""Typed exception hierarchy for core operations."""


class SabbaticalError(Exception):
    """Base class for all errors raised by core operations."""


class NotFoundError(SabbaticalError):
    def __init__(self, resource: str, identifier: str):
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} '{identifier}' not found.")


class ConflictError(SabbaticalError):
    """A state machine violation or uniqueness conflict.

    Examples: commenting on an in_progress task, creating a duplicate agent name.
    """


class ValidationError(SabbaticalError):
    """An input value failed validation.

    Examples: workspace path does not exist, name not snake_case.
    """

    def __init__(self, field: str, message: str):
        self.field = field
        super().__init__(f"{field}: {message}")


class PreconditionError(SabbaticalError):
    """A required precondition was not met.

    Examples: creating a task in an org with no root agent.
    """


class SchemaError(SabbaticalError):
    """Database schema is outdated. Raised by get_database_from_config()."""
