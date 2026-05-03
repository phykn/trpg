"""finalize() emits a `suggestions` SSE event using the server-side template
chips whenever a `to_front_fn` is given (matches the existing `state` event gate)."""

import pytest

from src.domain.entities import Character, Connection, Item, Location, Stats
from src.domain.state import CombatState, GameState
from src.flow.dirty import Dirty, finalize
from src.mapping.to_front import to_front_state


class _FakeRepo:
    async def save_entity(self, *a, **kw): pass
    async def append_log_entries(self, *a, **kw): pass
    async def append_history_entries(self, *a, **kw): pass
    async def append_dialogue_entries(self, *a, **kw): pass
    async def save_meta(self, *a, **kw): pass


def _state_with_npc_and_inventory() -> GameState:
    s = GameState(game_id="t", profile="default", player_id="player_01")
    s.locations["loc_a"] = Location(
        id="loc_a", name="현장", connections=[Connection(target_id="loc_b")]
    )
    s.locations["loc_b"] = Location(id="loc_b", name="광장")
    s.items["sword_01"] = Item(id="sword_01", name="검")
    s.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        gender="male",
        stats=Stats(),
        location_id="loc_a",
        inventory_ids=["sword_01"],
    )
    s.characters["npc_01"] = Character(
        id="npc_01",
        name="탈크",
        race_id="human",
        gender="male",
        stats=Stats(),
        location_id="loc_a",
    )
    return s


@pytest.mark.asyncio
async def test_finalize_emits_suggestions_event_with_template_chips():
    state = _state_with_npc_and_inventory()
    events = [
        ev async for ev in finalize(state, _FakeRepo(), Dirty(), to_front_state)
    ]
    sug = next(ev for ev in events if ev["type"] == "suggestions")
    items = sug["data"]["items"]
    assert len(items) == 3
    assert "탈크에게 말을 건다" in items
    assert "광장으로 이동한다" in items
    assert "검을 살펴본다" in items


@pytest.mark.asyncio
async def test_finalize_emits_empty_suggestions_in_combat():
    state = _state_with_npc_and_inventory()
    state.combat_state = CombatState()
    events = [
        ev async for ev in finalize(state, _FakeRepo(), Dirty(), to_front_state)
    ]
    sug = next(ev for ev in events if ev["type"] == "suggestions")
    assert sug["data"]["items"] == []


@pytest.mark.asyncio
async def test_finalize_skips_suggestions_event_without_to_front_fn():
    """No client payload requested → no suggestions event either (matches the
    existing `state` event gate). Engine-only test paths stay quiet."""
    state = _state_with_npc_and_inventory()
    events = [
        ev async for ev in finalize(state, _FakeRepo(), Dirty(), to_front_fn=None)
    ]
    types = [ev["type"] for ev in events]
    assert "suggestions" not in types
