from src.domain.entities import Character, Connection, Location, Stats
from src.domain.memory import PendingCheck
from src.flow.dirty import Dirty
from src.flow.roll import _apply_movement_roll_outcome


def _build_state(fresh_state):
    fresh_state.player_id = "player_01"
    fresh_state.locations["plaza_01"] = Location(
        id="plaza_01",
        name="광장",
        connections=[Connection(target_id="gate_01")],
    )
    fresh_state.locations["gate_01"] = Location(
        id="gate_01",
        name="성문",
        connections=[Connection(target_id="plaza_01")],
    )
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="주",
        race_id="human",
        stats=Stats(),
        location_id="plaza_01",
    )
    return fresh_state


def _pending(targets: list[str]) -> PendingCheck:
    return PendingCheck(
        player_input="가본다",
        tier="보통",
        stat="DEX",
        target="gate_01",
        targets=targets,
        dc=10,
        mod=0,
        required_roll=10,
        reason="",
        created_at="2026-01-01T00:00:00Z",
    )


def test_roll_movement_marks_destination_visited(fresh_state):
    # Movement-roll path goes through apply_changes with a `move` state_change.
    # The engine-level fix in _apply_move now centralizes the visited update
    # so this caller doesn't need to remember it.
    state = _build_state(fresh_state)
    pending = _pending(["gate_01"])
    _apply_movement_roll_outcome(state, pending, "success", Dirty())
    assert state.characters["player_01"].location_id == "gate_01"
    assert "gate_01" in state.characters["player_01"].visited_location_ids


def test_roll_movement_failure_does_not_visit(fresh_state):
    # A failed movement roll keeps the player in place — no visit recorded.
    state = _build_state(fresh_state)
    pending = _pending(["gate_01"])
    _apply_movement_roll_outcome(state, pending, "failure", Dirty())
    assert state.characters["player_01"].location_id == "plaza_01"
    assert "gate_01" not in state.characters["player_01"].visited_location_ids
