"""Wire-side label combiners — read GameState/GameGraph and produce
display-ready dicts/strings for the client payload. The locale-only
wrappers (single-shot render() calls with no game-state knowledge) live
in `locale/labels.py` instead."""

from typing import get_args

from src.game.domain.entities import Character, Stats
from src.game.domain.state import GameState
from src.game.domain.types import StatKey, Tier
from src.game.ontology.graph import GameGraph
from src.game.ontology.queries import giver_of, location_of, race_of
from src.locale import render
from src.locale.labels import stat_label


# Display order tied to StatKey definition.
_STAT_ORDER: tuple[StatKey, ...] = get_args(StatKey)


def stats_payload(stats: Stats) -> list[dict]:
    return [
        {"label": stat_label(key), "value": getattr(stats, key)} for key in _STAT_ORDER
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


# Risk badge: ASCII enum value → {label, tone} dict for client. Tone stays in
# Python (visual atom, not localized); only the label flows from the catalog.
_RISK_TONES: dict[str, str] = {"safe": "good", "risky": "neutral", "dangerous": "bad"}


def risk_payload(risk: str) -> dict:
    return {"label": render(f"ui.risk.{risk}.label", "ko"), "tone": _RISK_TONES.get(risk, "neutral")}


# `None` tone keeps the neutral mid-tier label uncolored on the panel.
_TIER_TONE: dict[Tier, str | None] = {
    "very_easy": "neutral",
    "easy": "good",
    "normal": None,
    "hard": "exp",
    "very_hard": "accent",
    "legend": "bad",
    "myth": "bad",
}


def difficulty_badge(tier: str) -> dict:
    return {"label": render(f"tier.{tier}", "ko"), "tone": _TIER_TONE.get(tier)}
