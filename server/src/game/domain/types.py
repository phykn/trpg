from typing import Literal, get_args


GraphStatKey = Literal["body", "agility", "mind", "presence"]
GRAPH_STAT_KEYS: tuple[GraphStatKey, ...] = ("body", "agility", "mind", "presence")


Tier = Literal[
    "very_easy",
    "easy",
    "normal",
    "hard",
    "very_hard",
    "legend",
    "myth",
]


_TIER_ORDER: tuple[str, ...] = get_args(Tier)


def tier_to_int(tier: Tier) -> int:
    return _TIER_ORDER.index(tier) + 1


Grade = Literal[
    "critical_success",
    "success",
    "partial_success",
    "failure",
    "critical_failure",
]


_SECRET_MASKED_GRADES: frozenset[str] = frozenset({"failure", "critical_failure"})


def is_secret_masked_grade(grade: str | None) -> bool:
    """True when narrate context must drop secret slots — data-layer enforcement of the failed-roll prompt rule."""
    return grade in _SECRET_MASKED_GRADES


Intent = Literal["friendly", "hostile", "deceptive"]


Phase = Literal["dawn", "morning", "afternoon", "night"]


EncounterRisk = Literal["safe", "risky", "dangerous"]
