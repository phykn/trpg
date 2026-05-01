"""Subject pin tracking when the player relocates."""

from src.domain.entities import Character, Location, Stats
from src.domain.memory import TurnLogEntry
from src.flow.subject import reconcile_subject_after_move


def _seed_two_locations(fresh_state):
    s = fresh_state
    s.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    s.locations["gate_01"] = Location(id="gate_01", name="성문")
    s.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        stats=Stats(STR=10, DEX=10, CON=10, INT=10, WIS=10, CHA=10),
        hp=20,
        max_hp=20,
        mp=10,
        max_mp=10,
        location_id="plaza_01",
    )
    return s


def _add_npc(state, *, cid, name, location_id, alive=True):
    state.characters[cid] = Character(
        id=cid,
        name=name,
        race_id="human",
        stats=Stats(STR=10, DEX=10, CON=10, INT=10, WIS=10, CHA=10),
        hp=10,
        max_hp=10,
        mp=0,
        max_mp=0,
        location_id=location_id,
        alive=alive,
    )


def test_keeps_pin_when_subject_at_same_location(fresh_state):
    s = _seed_two_locations(fresh_state)
    _add_npc(s, cid="barkeep", name="주인", location_id="plaza_01")
    s.active_subject_id = "barkeep"

    reconcile_subject_after_move(s)

    assert s.active_subject_id == "barkeep"


def test_swaps_to_first_alive_npc_at_new_location(fresh_state):
    s = _seed_two_locations(fresh_state)
    _add_npc(s, cid="barkeep", name="주인", location_id="plaza_01")
    _add_npc(s, cid="guard", name="문지기", location_id="gate_01")
    s.active_subject_id = "barkeep"
    s.characters["player_01"].location_id = "gate_01"

    reconcile_subject_after_move(s)

    assert s.active_subject_id == "guard"


def test_prefers_recent_npc_over_arbitrary_first(fresh_state):
    s = _seed_two_locations(fresh_state)
    _add_npc(s, cid="barkeep", name="주인", location_id="plaza_01")
    _add_npc(s, cid="guard_a", name="문지기A", location_id="gate_01")
    _add_npc(s, cid="guard_b", name="문지기B", location_id="gate_01")
    s.active_subject_id = "barkeep"
    s.characters["player_01"].location_id = "gate_01"
    s.turn_log.append(TurnLogEntry(turn=1, target="guard_b", summary="이전에 인사했음"))

    reconcile_subject_after_move(s)

    assert s.active_subject_id == "guard_b"


def test_clears_when_no_npc_at_new_location(fresh_state):
    s = _seed_two_locations(fresh_state)
    _add_npc(s, cid="barkeep", name="주인", location_id="plaza_01")
    s.active_subject_id = "barkeep"
    s.characters["player_01"].location_id = "gate_01"

    reconcile_subject_after_move(s)

    assert s.active_subject_id is None


def test_skips_dead_when_auto_picking(fresh_state):
    s = _seed_two_locations(fresh_state)
    _add_npc(s, cid="barkeep", name="주인", location_id="plaza_01")
    _add_npc(s, cid="corpse", name="시체", location_id="gate_01", alive=False)
    _add_npc(s, cid="guard", name="문지기", location_id="gate_01")
    s.active_subject_id = "barkeep"
    s.characters["player_01"].location_id = "gate_01"

    reconcile_subject_after_move(s)

    assert s.active_subject_id == "guard"


def test_clears_when_subject_id_no_longer_in_state(fresh_state):
    s = _seed_two_locations(fresh_state)
    s.active_subject_id = "ghost"

    reconcile_subject_after_move(s)

    assert s.active_subject_id is None


def test_noop_when_no_pin(fresh_state):
    s = _seed_two_locations(fresh_state)
    _add_npc(s, cid="guard", name="문지기", location_id="gate_01")
    s.active_subject_id = None
    s.characters["player_01"].location_id = "gate_01"

    reconcile_subject_after_move(s)

    assert s.active_subject_id is None
