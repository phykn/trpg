"""C1 — attempt_rest deducts cost_gold on entry, raises on insufficient."""

import pytest

from src.game.domain.entities import Character, Location, Race, Stats
from src.game.domain.errors import RestInsufficientGold
from src.game.domain.state import GameState
from src.game.engines.recovery import attempt_rest
from src.game.rules import RULES


def _make_state(actor_gold: int, hp: int = 1) -> GameState:
    state = GameState(game_id="t", profile="test", player_id="player")
    state.locations["safe_room"] = Location(
        id="safe_room",
        name="안전한 방",
        description="",
        sleep_risk="safe",
        sleep_encounters=[],
    )
    state.races["human"] = Race(id="human", name="인간", description="")
    actor = Character(
        id="player",
        name="주인공",
        race_id="human",
        stats=Stats(),
        gold=actor_gold,
        hp=hp,
        max_hp=20,
        mp=10,
        max_mp=15,
        location_id="safe_room",
    )
    state.characters[actor.id] = actor
    state.invalidate_graph()
    return state


@pytest.mark.asyncio
async def test_attempt_rest_deducts_cost_gold():
    state = _make_state(actor_gold=50)
    actor = state.characters[state.player_id]
    outcome, enemies = await attempt_rest(state, state.player_id)
    assert outcome == "full_recovery"
    assert actor.gold == 50 - RULES.recovery.cost_gold
    assert actor.hp == actor.max_hp
    assert actor.mp == actor.max_mp


@pytest.mark.asyncio
async def test_attempt_rest_charges_exact_cost_at_threshold():
    state = _make_state(actor_gold=RULES.recovery.cost_gold)
    actor = state.characters[state.player_id]
    outcome, _ = await attempt_rest(state, state.player_id)
    assert outcome == "full_recovery"
    assert actor.gold == 0


@pytest.mark.asyncio
async def test_attempt_rest_raises_on_insufficient_gold():
    state = _make_state(actor_gold=5)
    actor = state.characters[state.player_id]
    with pytest.raises(RestInsufficientGold):
        await attempt_rest(state, state.player_id)
    assert actor.gold == 5  # unchanged
    assert actor.hp == 1  # unchanged


@pytest.mark.asyncio
async def test_attempt_rest_raises_on_zero_gold():
    state = _make_state(actor_gold=0)
    with pytest.raises(RestInsufficientGold):
        await attempt_rest(state, state.player_id)
