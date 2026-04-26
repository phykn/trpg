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


class InventoryInvalid(DomainError):
    """장비/거래 요청이 슬롯/요구치/무게/affinity/잔여 골드 검증 통과 못 함."""

    pass


class SkillInvalid(DomainError):
    """cast 요청이 레벨·MP·사정거리·소유 검증 통과 못 함."""

    pass
