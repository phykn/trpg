"""Test that narrate's apply_changes + enforce_item_locality wire correctly."""

import pytest

from src.game.domain.entities import Character, Item, Location, Race, Stats
from src.game.domain.memory import GMLogEntry
from src.game.domain.state import GameState
from src.game.engines.invariants import enforce_item_locality
from src.game.flow.dirty import Dirty
from src.game.flow.narrate import consume_narrate
from src.llm.calls.narrate import NarrateOutput, NarrativeFinal


def _state() -> GameState:
    s = GameState(game_id="g_test", profile="p_test", player_id="player_01")
    s.races["race_human"] = Race(id="race_human", name="인간", description="인간 종족")
    s.locations["loc_01"] = Location(id="loc_01", name="광장")
    s.items["sword_01"] = Item(id="sword_01", name="검", weight=1, price=10)
    p = Character(
        id="player_01",
        name="당신",
        race_id="race_human",
        location_id="loc_01",
        stats=Stats(),
        is_player=True,
    )
    p.max_hp = p.hp = 20
    p.max_mp = p.mp = 10
    s.characters["player_01"] = p
    npc = Character(
        id="z_npc_01",
        name="상인",
        race_id="race_human",
        location_id="loc_01",
        stats=Stats(),
    )
    npc.max_hp = npc.hp = 20
    npc.max_mp = npc.mp = 10
    s.characters["z_npc_01"] = npc
    return s


def test_enforce_after_simulated_llm_duplicate_set():
    """Simulate LLM-emitted state_changes that result in duplication; enforcer cleans up."""
    state = _state()
    # Simulate the bug: player got the sword, but NPC equipment still references it.
    state.characters["player_01"].inventory_ids.append("sword_01")
    state.characters["z_npc_01"].equipment.weapon = "sword_01"

    dirty: set[tuple[str, str]] = set()
    warnings = enforce_item_locality(state, dirty=dirty)

    assert len(warnings) == 1
    # Player keeps it (player_01 < z_npc_01 alphabetically).
    assert "sword_01" in state.characters["player_01"].inventory_ids
    assert state.characters["z_npc_01"].equipment.weapon is None
    assert ("characters", "z_npc_01") in dirty


@pytest.mark.asyncio
async def test_consume_narrate_does_not_leak_locality_warning_to_player_log(capsys):
    """Pre-fix: enforce_item_locality warnings landed in the GM log as raw English
    text containing entity ids ('item X was duplicated; kept characters/Y/...').
    Now they must go to the diag stderr channel only, never to dirty.log / state.log_entries."""
    state = _state()
    state.characters["player_01"].inventory_ids.append("sword_01")
    state.characters["z_npc_01"].equipment.weapon = "sword_01"

    final = NarrativeFinal(body="좋습니다.", output=NarrateOutput())

    async def _stream():
        yield final

    dirty = Dirty()
    events = [
        ev
        async for ev in consume_narrate(
            state,
            dirty,
            _stream(),
            target_for_log=None,
            dialogue_input=None,
        )
    ]

    # State-side repair still happens.
    assert state.characters["z_npc_01"].equipment.weapon is None

    # No GM log entry carries the raw English warning.
    for entry in dirty.log:
        if isinstance(entry, GMLogEntry):
            assert "duplicated" not in entry.text
            assert "sword_01" not in entry.text
            assert "characters/" not in entry.text
    for ev in events:
        if ev.get("type") == "log_entry":
            text = ev["data"].get("text", "")
            assert "duplicated" not in text
            assert "sword_01" not in text
            assert "characters/" not in text

    # Routed to diag stderr instead.
    captured = capsys.readouterr()
    assert "narrate:item_locality_repair" in captured.err
