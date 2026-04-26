from typing import Literal


StatKey = Literal["STR", "DEX", "CON", "INT", "WIS", "CHA"]


Tier = Literal[
    "매우 쉬움",
    "쉬움",
    "보통",
    "어려움",
    "매우 어려움",
    "전설",
    "신화",
]


Grade = Literal[
    "critical_success",
    "success",
    "partial_success",
    "failure",
    "critical_failure",
]


Intent = Literal["friendly", "hostile", "deceptive"]


Action = Literal["pass", "roll", "combat", "rest", "use", "clarify", "reject"]
