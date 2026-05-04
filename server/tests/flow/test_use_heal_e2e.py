"""Receipt-path heal: emit_use on hp=1/20 player + 약초 ⇒ hp=16."""

import pytest

from src.domain.entities import (
    Character,
    ConsumableEffect,
    Item,
    Location,
    Race,
    Stats,
)
from src.domain.state import GameState
from src.flow.actions import emit_use
from src.flow.dirty import Dirty


@pytest.mark.asyncio
async def test_emit_use_heal_mutates_hp():
    """Direct emit_use path — no LLM, no SSE. Locks the engine invariant
    that the spec's §6 regression depends on."""
    state = GameState(game_id="g", profile="p", player_id="player_01")
    state.locations["loc_01"] = Location(id="loc_01", name="광장")
    state.races["human"] = Race(id="human", name="인간", description="")
    state.items["herb_01"] = Item(
        id="herb_01",
        name="약초 꾸러미",
        consumable=True,
        effects=ConsumableEffect(type="consumable", effect="heal", amount=15),
    )
    player = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        stats=Stats(),
        location_id="loc_01",
        hp=1,
        max_hp=20,
        inventory_ids=["herb_01"],
    )
    state.characters["player_01"] = player
    dirty = Dirty()

    events: list[dict] = []
    async for ev in emit_use(state, "player_01", "herb_01", None, dirty):
        events.append(ev)

    assert player.hp == 16
    assert "herb_01" not in player.inventory_ids  # consumed
    log_texts = [e["data"]["text"] for e in events if e.get("type") == "log_entry"]
    assert any("(15 회복)" in t for t in log_texts)
