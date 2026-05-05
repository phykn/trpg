"""surroundings top-level: companions list and companions_max."""

from src.llm.context.surroundings import build_surroundings
from src.domain.entities import Character, Location, Race, Stats
from src.domain.state import GameState
from src.rules import RULES


def _make_state() -> GameState:
    state = GameState(game_id="g", profile="p", player_id="player_01")
    state.locations["loc_01"] = Location(id="loc_01", name="광장")
    state.races["human"] = Race(id="human", name="인간", description="")
    state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        stats=Stats(),
        location_id="loc_01",
    )
    state.characters["ally_01"] = Character(
        id="ally_01",
        name="동료",
        race_id="human",
        stats=Stats(),
        location_id="loc_01",
    )
    return state


def test_companions_empty_when_no_companions():
    state = _make_state()
    sur = build_surroundings(state, "player_01")
    assert sur["companions"] == []


def test_companions_contains_correct_ids():
    state = _make_state()
    state.characters["player_01"].companions.append("ally_01")
    sur = build_surroundings(state, "player_01")
    assert "ally_01" in sur["companions"]
    assert len(sur["companions"]) == 1


def test_companions_max_matches_rules():
    state = _make_state()
    sur = build_surroundings(state, "player_01")
    assert sur["companions_max"] == RULES.companions.max_companions


def test_companions_present_on_no_location_branch():
    state = _make_state()
    state.characters["player_01"].location_id = None
    state.characters["player_01"].companions.append("ally_01")
    sur = build_surroundings(state, "player_01")
    assert "companions" in sur
    assert "companions_max" in sur
    assert "ally_01" in sur["companions"]
