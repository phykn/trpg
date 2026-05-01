"""Display-label helpers shared by `to_front` (FrontState builder) and
`story_graph` (graph projection). Pure transforms — entity/relation in,
Korean string or static-payload out, no IO."""

from ..domain.entities import Character, Stats
from ..domain.state import GameState
from ..ontology.graph import GameGraph
from ..ontology.queries import race_of


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
    """Race name resolved via the `belongs_to_race` edge — falls back to the
    raw race id when the relation points at a missing race entity."""
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


# Risk payload mirrors the client's `RiskBadge`: each entry is
# `{label, tone}` so the panel renders the colored chip without
# re-deriving from the raw enum.
RISK_PAYLOAD: dict[str, dict] = {
    "safe": {"label": "안전", "tone": "good"},
    "risky": {"label": "주의", "tone": "neutral"},
    "dangerous": {"label": "위험", "tone": "bad"},
}
