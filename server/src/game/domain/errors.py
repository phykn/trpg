class DomainError(Exception):
    """Base for all domain errors. The API layer maps these to HTTP/SSE responses."""


class PendingCheckActive(DomainError):
    pass


class PendingCheckExpected(DomainError):
    pass


class PendingConfirmationActive(DomainError):
    pass


class PendingConfirmationExpected(DomainError):
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


class ProfileMalformed(DomainError):
    """Seed JSON in the profile points at ids that don't exist in the profile."""

    pass


class LevelUpInvalid(DomainError):
    """level_up request failed validation (pair-trade / cap / remaining xp etc.)."""

    pass


class InventoryInvalid(DomainError):
    """equip/trade request failed validation (slot / requirements / weight / affinity / gold)."""

    pass


class SkillInvalid(DomainError):
    """cast request failed validation (level / MP / range / ownership)."""

    pass


class CombatStateInvalid(DomainError):
    """Tried to enter combat while combat_state is already set, or any other
    state-machine inconsistency around combat lifecycle."""

    pass


class RestInsufficientGold(DomainError):
    """Rest attempt failed because the actor has fewer gold than RULES.recovery.cost_gold."""

    pass
