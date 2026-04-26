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


class LevelUpInvalid(DomainError):
    """level_up 요청이 페어 트레이드/캡/잔여 xp 등의 검증을 통과 못 함."""

    pass
