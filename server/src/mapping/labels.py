from ..domain.entities import Character, Stats
from ..domain.state import GameState
from ..ontology.graph import GameGraph
from ..ontology.queries import giver_of, location_of, race_of


_STAT_LABELS: tuple[tuple[str, str], ...] = (
    ("STR", "근력"),
    ("DEX", "민첩"),
    ("CON", "건강"),
    ("INT", "지능"),
    ("WIS", "지혜"),
    ("CHA", "매력"),
)
_STAT_LABEL_BY_KEY: dict[str, str] = dict(_STAT_LABELS)


def stat_label(stat: str) -> str:
    return _STAT_LABEL_BY_KEY.get(stat, stat)


def stats_payload(stats: Stats) -> list[dict]:
    return [
        {"label": label, "value": getattr(stats, key)} for key, label in _STAT_LABELS
    ]


def race_label(state: GameState, graph: GameGraph, char_id: str) -> str:
    """Race name via the `belongs_to_race` edge; falls back to the raw race id when the entity is missing."""
    race_id = race_of(graph, char_id)
    if race_id is None:
        return ""
    race = state.races.get(race_id)
    return race.name if race is not None else race_id


def race_job_label(state: GameState, graph: GameGraph, char: Character) -> str:
    """`<race> · <job>` if the character has a job, otherwise just `<race>`."""
    race = race_label(state, graph, char.id)
    return f"{race} · {char.job}" if char.job else race


def gender_label(char: Character) -> str:
    """Korean label for display, empty for non-sexed entities."""
    if char.gender == "male":
        return "남성"
    if char.gender == "female":
        return "여성"
    return ""


def giver_with_location_label(state: GameState, graph: GameGraph, quest_id: str) -> str:
    """`<giver name> (<location name>)`. Falls back to giver name without location, or empty string if no giver."""
    giver_id = giver_of(graph, quest_id)
    if giver_id is None:
        return ""
    giver = state.characters.get(giver_id)
    if giver is None:
        return giver_id
    loc_id = location_of(graph, giver_id)
    loc = state.locations.get(loc_id) if loc_id is not None else None
    if loc is None:
        return giver.name
    return f"{giver.name} ({loc.name})"


RISK_PAYLOAD: dict[str, dict] = {
    "safe": {"label": "안전", "tone": "good"},
    "risky": {"label": "주의", "tone": "neutral"},
    "dangerous": {"label": "위험", "tone": "bad"},
}


# `None` tone keeps the neutral mid-tier label uncolored on the panel.
_TIER_TONE: dict[str, str | None] = {
    "매우 쉬움": "neutral",
    "쉬움": "good",
    "보통": None,
    "어려움": "exp",
    "매우 어려움": "accent",
    "전설": "bad",
    "신화": "bad",
}


def difficulty_badge(tier: str) -> dict:
    return {"label": tier, "tone": _TIER_TONE.get(tier)}
