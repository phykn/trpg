"""push_act with turn_summary appends a turn_log entry alongside the act line.
Receipt actions (equip / unequip / use-self) must surface in next-turn engine
context (turn_log feeds judge / extract); without this the system card and the
narrative history diverge."""

import pytest

from src.game.domain.entities import (
    Character,
    ConsumableEffect,
    Item,
    Location,
    Stats,
    WeaponEffect,
)
from src.game.domain.state import GameState
from src.game.flow.actions import emit_equip, emit_unequip, emit_use
from src.game.flow.dirty import Dirty, push_act


def _seed() -> GameState:
    s = GameState(game_id="t", profile="default", player_id="player_01")
    s.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    s.items["sword_01"] = Item(
        id="sword_01",
        name="단검",
        effects=WeaponEffect(type="weapon", weapon_dice="1d6"),
    )
    s.items["potion_01"] = Item(
        id="potion_01",
        name="치유 물약",
        consumable=True,
        effects=ConsumableEffect(type="consumable", effect="heal", amount=8),
    )
    s.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        location_id="plaza_01",
        stats=Stats(),
        hp=10,
        max_hp=20,
        mp=5,
        max_mp=10,
        inventory_ids=["sword_01", "potion_01"],
    )
    return s


def test_push_act_with_turn_summary_appends_turn_log():
    state = _seed()
    dirty = Dirty()
    starting_turn_log_len = len(state.turn_log)
    push_act(state, dirty, "engine line", turn_summary="요약", target=None)
    assert len(state.turn_log) == starting_turn_log_len + 1
    assert state.turn_log[-1].summary == "요약"
    assert state.turn_log[-1].target is None
    assert dirty.history[-1].summary == "요약"


def test_push_act_without_turn_summary_does_not_touch_turn_log():
    state = _seed()
    dirty = Dirty()
    starting_turn_log_len = len(state.turn_log)
    push_act(state, dirty, "engine line")
    assert len(state.turn_log) == starting_turn_log_len
    assert dirty.history == []


@pytest.mark.asyncio
async def test_emit_equip_pushes_turn_log():
    state = _seed()
    dirty = Dirty()
    async for _ev in emit_equip(state, "player_01", "sword_01", dirty):
        pass
    assert any("단검 착용" in e.summary for e in state.turn_log), state.turn_log


@pytest.mark.asyncio
async def test_emit_unequip_pushes_turn_log():
    state = _seed()
    state.characters["player_01"].equipment.weapon = "sword_01"
    dirty = Dirty()
    async for _ev in emit_unequip(state, "player_01", "sword_01", dirty):
        pass
    assert any("단검 해제" in e.summary for e in state.turn_log), state.turn_log


@pytest.mark.asyncio
async def test_emit_use_self_pushes_turn_log():
    state = _seed()
    dirty = Dirty()
    async for _ev in emit_use(state, "player_01", "potion_01", None, dirty):
        pass
    assert any("치유 물약 사용" in e.summary for e in state.turn_log), state.turn_log
