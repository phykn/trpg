"""Per-agent trim helpers drop fields the agent doesn't read."""

from src.context.surroundings import (
    surroundings_for_extract,
    surroundings_for_narrate_body,
)


def _full() -> dict:
    return {
        "location": {"id": "loc"},
        "entities": [],
        "corpses": [],
        "skills": [{"name": "휘두르기"}],
        "inventory": [],
        "merchants": [],
        "equipment": {"weapon": None},
        "in_combat": False,
        "growth": {"can_level_up": False},
        "recent_npc": None,
    }


def test_narrate_body_trim_drops_skills_equipment_in_combat():
    out = surroundings_for_narrate_body(_full())
    for k in ("skills", "equipment", "in_combat"):
        assert k not in out
    for k in ("location", "entities", "corpses", "inventory", "merchants", "growth", "recent_npc"):
        assert k in out


def test_extract_trim_keeps_only_valid_id_sources():
    out = surroundings_for_extract(_full())
    assert set(out.keys()) == {"entities", "corpses", "merchants"}
