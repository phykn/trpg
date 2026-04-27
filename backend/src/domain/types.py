from typing import Literal


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


_TIER_ORDER: tuple[Tier, ...] = (
    "매우 쉬움",
    "쉬움",
    "보통",
    "어려움",
    "매우 어려움",
    "전설",
    "신화",
)


def tier_to_int(tier: Tier) -> int:
    return _TIER_ORDER.index(tier) + 1


Grade = Literal[
    "critical_success",
    "success",
    "partial_success",
    "failure",
    "critical_failure",
]


Intent = Literal["friendly", "hostile", "deceptive"]
