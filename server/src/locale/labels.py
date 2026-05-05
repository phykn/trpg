"""Pure locale wrappers — render the catalog with no game-state knowledge.

Functions and module-level constants here only call `render()`. They take
plain strings or numbers, not domain objects, so locale/ stays foundational
(no upward dependency on game/).

Wire-side label combiners that *do* read GameState/GameGraph live in
`wire/labels.py` instead.
"""

from .render import render


def stat_label(stat: str) -> str:
    """Korean display label for a stat key. Falls back to the raw key for unknown values."""
    try:
        return render(f"stat.{stat}", "ko")
    except KeyError:
        return stat


def gender_label(gender: str) -> str:
    """Korean label for display, empty for non-sexed entities."""
    if gender == "male":
        return render("ui.gender.male", "ko")
    if gender == "female":
        return render("ui.gender.female", "ko")
    return ""


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
