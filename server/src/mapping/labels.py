from typing import get_args

from ..domain.entities import Character, Stats
from ..domain.state import GameState
from ..domain.types import StatKey, Tier
from ..locale import render
from ..ontology.graph import GameGraph
from ..ontology.queries import giver_of, location_of, race_of


# Display order tied to StatKey definition.
_STAT_ORDER: tuple[StatKey, ...] = get_args(StatKey)


def stat_label(stat: str) -> str:
    """Korean display label for a stat key. Falls back to the raw key for unknown values."""
    try:
        return render(f"stat.{stat}", "ko")
    except KeyError:
        return stat


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


def gender_label(char: Character) -> str:
    """Korean label for display, empty for non-sexed entities."""
    if char.gender == "male":
        return render("ui.gender.male", "ko")
    if char.gender == "female":
        return render("ui.gender.female", "ko")
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


# ----- Story-graph edge labels (rendered on client map) -----

STORY_EDGE_LABEL_CURRENT = render("ui.story.edge.current", "ko")
STORY_EDGE_LABEL_OBSERVE = render("ui.story.edge.observe", "ko")
STORY_EDGE_LABEL_PROGRESS = render("ui.story.edge.progress", "ko")
STORY_EDGE_LABEL_MOVE = render("ui.story.edge.move", "ko")
STORY_EDGE_LABEL_MEET = render("ui.story.edge.meet", "ko")
STORY_EDGE_LABEL_QUEST_GIVER = render("ui.story.edge.quest_giver", "ko")
STORY_EDGE_LABEL_QUEST_TARGET = render("ui.story.edge.quest_target", "ko")


# ----- Story-graph summary line parts -----

STORY_SUMMARY_HERO = render("ui.story.summary.hero", "ko")
STORY_SUMMARY_EMPTY = render("ui.story.summary.empty", "ko")


def story_summary_quest(title: str) -> str:
    return render("ui.story.summary.quest", "ko", title=title)


def story_summary_location(name: str) -> str:
    return render("ui.story.summary.location", "ko", name=name)


def story_summary_entities(count: int) -> str:
    return render("ui.story.summary.entities", "ko", count=count)


def story_summary_places(count: int) -> str:
    return render("ui.story.summary.places", "ko", count=count)


# ----- Default fallback for action reasons surfaced in the GM log -----

ROLL_REASON_DEFAULT = render("ui.roll.reason_default", "ko")


# ----- NPC state tags surfaced to the judge prompt -----


def state_tag_friendly(affinity: int) -> str:
    return render("ui.state.friendly", "ko", affinity=affinity)


def state_tag_wary(affinity: int) -> str:
    return render("ui.state.wary", "ko", affinity=affinity)


def state_tag_wounded(hp_pct: int) -> str:
    return render("ui.state.wounded", "ko", hp_pct=hp_pct)
