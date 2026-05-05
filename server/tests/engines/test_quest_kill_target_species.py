"""D1 fix — _trigger_matches accepts race match with location-adjacency guard.

Dynamic spawn enemies (different runtime id, same race as the seed) should
advance the quest when they die in the expected location or an adjacent
one. Non-adjacent kills must NOT advance the quest, even with race match.
"""

from src.domain.entities import (
    Character,
    CombatBehavior,
    Connection,
    Location,
    Quest,
    QuestTrigger,
    Race,
    Stats,
)
from src.domain.state import GameState
from src.engines.quest import _trigger_matches


def _make_state() -> GameState:
    """Two adjacent locations, a goblin race, a quest targeting a goblin
    seed at mountain_road, plus a non-adjacent location for the negative case."""
    state = GameState(game_id="t", profile="test", player_id="player_01")
    state.locations["mountain_road"] = Location(
        id="mountain_road",
        name="산문 길",
        description="",
        connections=[Connection(target_id="isnar_square")],
    )
    state.locations["isnar_square"] = Location(
        id="isnar_square",
        name="이스나르 광장",
        description="",
        connections=[Connection(target_id="mountain_road")],
    )
    state.locations["far_field"] = Location(
        id="far_field",
        name="먼 들판",
        description="",
        connections=[],
    )
    state.races["goblin"] = Race(id="goblin", name="고블린", description="")
    state.races["human"] = Race(id="human", name="인간", description="")
    state.characters["goblin_seed"] = Character(
        id="goblin_seed",
        name="고블린 정찰병",
        race_id="goblin",
        stats=Stats(),
        location_id="mountain_road",
        combat_behavior=CombatBehavior(),
    )
    state.quests["q_chief_request"] = Quest(
        id="q_chief_request",
        title="촌장의 부탁",
        giver_id="edrik",
        difficulty="easy",
        triggers=[
            QuestTrigger(
                id="t0",
                name="goblin slain",
                type="character_death",
                target_id="goblin_seed",
            )
        ],
        status="active",
    )
    state.invalidate_graph()
    return state


def _make_dynamic_goblin(
    state: GameState, *, char_id: str, location_id: str
) -> Character:
    raider = Character(
        id=char_id,
        name="동적 고블린",
        race_id="goblin",
        stats=Stats(),
        location_id=location_id,
        combat_behavior=CombatBehavior(),
    )
    state.characters[char_id] = raider
    state.invalidate_graph()
    return raider


def test_exact_id_match_passes():
    state = _make_state()
    trig = state.quests["q_chief_request"].triggers[0]
    assert _trigger_matches(state, trig, "character_death", "goblin_seed") is True


def test_same_location_combat_behavior_match_passes():
    state = _make_state()
    _make_dynamic_goblin(
        state, char_id="dyn_goblin_at_mountain", location_id="mountain_road"
    )
    trig = state.quests["q_chief_request"].triggers[0]
    assert (
        _trigger_matches(state, trig, "character_death", "dyn_goblin_at_mountain")
        is True
    )


def test_race_match_at_adjacent_location_passes():
    state = _make_state()
    _make_dynamic_goblin(
        state, char_id="dyn_goblin_at_square", location_id="isnar_square"
    )
    trig = state.quests["q_chief_request"].triggers[0]
    assert (
        _trigger_matches(state, trig, "character_death", "dyn_goblin_at_square") is True
    )


def test_race_match_at_distant_location_rejects():
    state = _make_state()
    _make_dynamic_goblin(state, char_id="dyn_goblin_far", location_id="far_field")
    trig = state.quests["q_chief_request"].triggers[0]
    assert _trigger_matches(state, trig, "character_death", "dyn_goblin_far") is False


def test_race_mismatch_at_adjacent_rejects():
    """A different-race hostile at an adjacent location must NOT advance the
    quest — only the existing same-location fallback or the new race-match
    branch can fire, and an off-race victim satisfies neither."""
    state = _make_state()
    state.characters["dyn_human"] = Character(
        id="dyn_human",
        name="떠돌이",
        race_id="human",
        stats=Stats(),
        location_id="isnar_square",
        combat_behavior=CombatBehavior(),
    )
    state.invalidate_graph()
    trig = state.quests["q_chief_request"].triggers[0]
    assert _trigger_matches(state, trig, "character_death", "dyn_human") is False


def test_race_match_without_combat_behavior_rejects():
    """A peaceful (combat_behavior=None) goblin in the same area is not a
    valid quest target — the existing combat_behavior gate stays."""
    state = _make_state()
    state.characters["dyn_peaceful"] = Character(
        id="dyn_peaceful",
        name="평범한 고블린",
        race_id="goblin",
        stats=Stats(),
        location_id="mountain_road",
        combat_behavior=None,
    )
    state.invalidate_graph()
    trig = state.quests["q_chief_request"].triggers[0]
    assert _trigger_matches(state, trig, "character_death", "dyn_peaceful") is False


def test_non_character_death_event_rejects():
    state = _make_state()
    trig = state.quests["q_chief_request"].triggers[0]
    assert _trigger_matches(state, trig, "item_acquired", "goblin_seed") is False
