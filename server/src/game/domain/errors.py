class DomainError(Exception):
    """Base for all domain errors. The API layer maps these to HTTP/SSE responses."""


class LLMUnavailable(DomainError):
    pass


class PersistenceFailed(DomainError):
    pass


class ProfileNotFound(DomainError):
    pass


class RaceNotFound(DomainError):
    pass


class ProfileMalformed(DomainError):
    """Seed JSON in the profile points at ids that don't exist in the profile."""

    pass
