"""Reachable is decided once on server based on adjacency from current location."""

from src.game.domain.entities import Character, Connection, Location, Stats
from src.wire.story_graph import to_story_graph


def _base_state(fresh_state):
    s = fresh_state
    s.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        stats=Stats(),
        location_id="loc_a",
    )
    s.locations["loc_a"] = Location(
        id="loc_a",
        name="마을",
        connections=[Connection(target_id="loc_b")],
    )
    s.locations["loc_b"] = Location(
        id="loc_b",
        name="숲",
        connections=[Connection(target_id="loc_c")],
    )
    s.locations["loc_c"] = Location(id="loc_c", name="산")
    return s


def test_current_location_reachable(fresh_state):
    state = _base_state(fresh_state)
    out = to_story_graph(state)
    nodes = {n["id"]: n for n in out["nodes"]}
    assert nodes["loc_a"]["kind"] == "place"
    assert nodes["loc_a"]["reachable"] is True


def test_adjacent_location_reachable(fresh_state):
    # loc_a → loc_b edge; hero at loc_a → loc_b is reachable
    state = _base_state(fresh_state)
    out = to_story_graph(state)
    nodes = {n["id"]: n for n in out["nodes"]}
    assert nodes["loc_b"]["kind"] == "location"
    assert nodes["loc_b"]["reachable"] is True
    assert nodes["loc_b"]["status"] == "reachable_move"


def test_non_adjacent_location_unreachable(fresh_state):
    # loc_c is two hops from loc_a (loc_a→loc_b→loc_c); not directly adjacent
    state = _base_state(fresh_state)
    out = to_story_graph(state)
    nodes = {n["id"]: n for n in out["nodes"]}
    assert nodes["loc_c"]["kind"] == "location"
    assert nodes["loc_c"]["reachable"] is False
    assert nodes["loc_c"]["status"] == "unreachable_move"
