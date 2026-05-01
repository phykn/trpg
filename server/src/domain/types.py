from typing import Literal, get_args


StatKey = Literal["STR", "DEX", "CON", "INT", "WIS", "CHA"]


# Pair-trade: stat_up → the stat that must be reduced together. Bidirectional. Shared by judge / growth / encounter.
STAT_PAIRS: dict[StatKey, StatKey] = {
    "STR": "CHA",
    "CHA": "STR",
    "DEX": "WIS",
    "WIS": "DEX",
    "CON": "INT",
    "INT": "CON",
}


Tier = Literal[
    "매우 쉬움",
    "쉬움",
    "보통",
    "어려움",
    "매우 어려움",
    "전설",
    "신화",
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
    """True when narrate context builders must drop secret slots (NPC inner
    state, quest reward detail, hidden affinity tags). The narrate prompt
    forbids leaking those on a failed roll, but prompt rules drift; the
    builder honors the same gate at the data layer so the LLM never sees
    the data it would have leaked."""
    return grade in _SECRET_MASKED_GRADES


Intent = Literal["friendly", "hostile", "deceptive"]
