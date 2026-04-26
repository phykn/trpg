class DomainError(Exception):
    """Base for all domain errors. The API layer maps these to HTTP/SSE responses."""


class PendingCheckActive(DomainError):
    pass


class PendingCheckExpected(DomainError):
    pass


class JudgeMalformed(DomainError):
    pass


class LLMUnavailable(DomainError):
    pass


class PersistenceFailed(DomainError):
    pass


class ProfileNotFound(DomainError):
    pass


class RaceNotFound(DomainError):
    pass
