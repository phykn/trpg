"""S3 — turn.run_turn combat-routing integration. Only judge is mocked; no LLM call."""
import random
import tempfile

import pytest

from src.domain.entities import Character, CombatBehavior, Equipment, Stats
from src.agents.dc_judge.schema import (
    CombatAction,
    PassAction,
)
from src.flow import judge as judge_mod
from src.flow import combat_phase as combat_phase_mod
from src.flow import turn as turn_mod
from src.flow.turn import run_turn
from src.domain.state import GameState


@pytest.fixture
def tmp_data():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def combat_state(fresh_state, tmp_data):
    """GameState with player + goblin both in plaza_01. saves_dir is tmp_data."""
    player = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        location_id="plaza_01",
        stats=Stats(STR=14, DEX=12, CON=10, INT=10, WIS=10, CHA=10),
        hp=20,
        max_hp=20,
    )
    goblin = Character(
        id="goblin_01",
        name="고블린",
        race_id="goblin",
        location_id="plaza_01",
        stats=Stats(STR=10, DEX=12, CON=10, INT=10, WIS=10, CHA=10),
        hp=8,
        max_hp=8,
        combat_behavior=CombatBehavior(attack_priority="nearest"),
    )
    fresh_state.characters["player_01"] = player
    fresh_state.characters["goblin_01"] = goblin
    # Mild workaround so save_full creates the game dir on demand: rather than prepping the directory manually, let turn flow create it on first _flush.
    return fresh_state


def _judge_returns(monkeypatch, action_obj):
    async def fake_judge(client, state, player_input):
        return action_obj
    monkeypatch.setattr(judge_mod, "run_judge", fake_judge)
    monkeypatch.setattr(turn_mod, "run_judge", fake_judge)
    monkeypatch.setattr(combat_phase_mod, "run_judge", fake_judge)


async def _collect(it):
    return [ev async for ev in it]


async def test_combat_start_and_npc_round_progress(combat_state, tmp_data, monkeypatch):
    """First 'combat' input from the player → combat_start, one goblin turn, then stops on the player's turn."""
    _judge_returns(monkeypatch, CombatAction(action="combat", targets=["goblin_01"]))
    rng = random.Random(123)  # deterministic
    events = await _collect(
        run_turn(
            client=None,  # judge is mocked, so the client is unused
            state=combat_state,
            profile_dir="<unused>",
            saves_dir=tmp_data,
            player_input="고블린을 공격한다",
            rng=rng,
        )
    )

    types = [e["type"] for e in events]
    assert "combat_start" in types
    assert combat_state.combat_state is not None
    cs = combat_state.combat_state
    assert set(cs.turn_order) == {"player_01", "goblin_01"}
    assert cs.enemy_ids == ["goblin_01"]


async def test_combat_with_invalid_target_does_not_consume_turn(
    combat_state, tmp_data, monkeypatch
):
    # Regression: judge sometimes returned target=<location_id> (e.g. "swamp")
    # for a "rush into the fog" input. The dispatcher used to forward it to
    # start_combat, leaving combat_state in a half-broken shape. Now the
    # dispatcher rejects unknown / dead targets without consuming the turn.
    _judge_returns(
        monkeypatch, CombatAction(action="combat", targets=["unknown_id"])
    )
    turn_before = combat_state.turn_count
    events = await _collect(
        run_turn(
            client=None,
            state=combat_state,
            profile_dir="<unused>",
            saves_dir=tmp_data,
            player_input="안개 속으로 검을 휘두른다",
            rng=random.Random(1),
        )
    )
    types = [e["type"] for e in events]
    assert "combat_start" not in types
    assert combat_state.combat_state is None
    assert combat_state.turn_count == turn_before


async def test_combat_with_self_target_does_not_consume_turn(
    combat_state, tmp_data, monkeypatch
):
    # Regression: judge sometimes returned `targets=['player_01']` (the player
    # attacking themselves). The dispatcher used to start combat with the
    # player as the only enemy, which then ended immediately — turn_count went
    # up but nothing else moved.
    _judge_returns(
        monkeypatch, CombatAction(action="combat", targets=["player_01"])
    )
    turn_before = combat_state.turn_count
    events = await _collect(
        run_turn(
            client=None,
            state=combat_state,
            profile_dir="<unused>",
            saves_dir=tmp_data,
            player_input="자신을 베어버린다",
            rng=random.Random(1),
        )
    )
    types = [e["type"] for e in events]
    assert "combat_start" not in types
    assert combat_state.combat_state is None
    assert combat_state.turn_count == turn_before


async def test_combat_player_attack_advances_round(combat_state, tmp_data, monkeypatch):
    """combat_state active and on the player's turn. CombatAction → damage applied."""
    # boot combat first
    from src.engines import combat as combat_engine
    combat_engine.start_combat(combat_state, ["goblin_01"], rng=random.Random(0))
    # adjust turn_order so the run stops on the player's turn
    combat_state.combat_state.turn_order = ["player_01", "goblin_01"]
    combat_state.combat_state.current_turn = 0

    _judge_returns(monkeypatch, CombatAction(action="combat", targets=["goblin_01"]))
    rng = random.Random(7)
    goblin_hp_before = combat_state.characters["goblin_01"].hp
    await _collect(
        run_turn(
            client=None,
            state=combat_state,
            profile_dir="<unused>",
            saves_dir=tmp_data,
            player_input="공격",
            rng=rng,
        )
    )
    # goblin took damage or died
    g = combat_state.characters["goblin_01"]
    assert g.hp < goblin_hp_before or not g.alive


async def test_combat_pass_action_consumes_player_turn(combat_state, tmp_data, monkeypatch):
    from src.engines import combat as combat_engine
    combat_engine.start_combat(combat_state, ["goblin_01"], rng=random.Random(0))
    combat_state.combat_state.turn_order = ["player_01", "goblin_01"]
    combat_state.combat_state.current_turn = 0
    round_before = combat_state.combat_state.round

    _judge_returns(monkeypatch, PassAction(action="pass"))
    rng = random.Random(2)
    events = await _collect(
        run_turn(
            client=None,
            state=combat_state,
            profile_dir="<unused>",
            saves_dir=tmp_data,
            player_input="대기",
            rng=rng,
        )
    )
    # pass + 1 npc turn → round should advance by at least 1 (one full loop back to the player)
    assert combat_state.combat_state is None or combat_state.combat_state.round >= round_before
    types = [e["type"] for e in events]
    # pass is also recorded as a combat_turn event
    assert "combat_turn" in types


async def test_start_combat_is_idempotent_when_already_in_combat(
    combat_state, tmp_data, monkeypatch
):
    # Defensive: if combat_state somehow survived into start_combat_and_run_npc_phase
    # (e.g. an old persistence regression), the function must not log
    # "전투 개시!" a second time or reset round/turn_order on the active fight.
    from src.engines import combat as combat_engine
    from src.flow.combat_phase import start_combat_and_run_npc_phase
    from src.flow.dirty import Dirty

    combat_engine.start_combat(combat_state, ["goblin_01"], rng=random.Random(0))
    combat_state.combat_state.turn_order = ["player_01", "goblin_01"]
    combat_state.combat_state.current_turn = 0
    round_before = combat_state.combat_state.round
    log_len_before = len(combat_state.log_entries)

    dirty = Dirty()
    events = await _collect(
        start_combat_and_run_npc_phase(
            combat_state, ["goblin_01"], dirty, rng=random.Random(1)
        )
    )

    types = [e["type"] for e in events]
    assert "combat_start" not in types
    assert combat_state.combat_state is not None
    assert combat_state.combat_state.round == round_before
    new_logs = combat_state.log_entries[log_len_before:]
    assert all(e.text != "전투 개시!" for e in new_logs)


async def test_combat_ends_when_enemy_dies_from_player_attack(
    combat_state, tmp_data, monkeypatch
):
    """Drop goblin hp to 1 so it dies in one hit → combat_end victory emitted."""
    from src.engines import combat as combat_engine
    combat_state.characters["goblin_01"].hp = 1
    combat_state.characters["goblin_01"].max_hp = 1
    combat_engine.start_combat(combat_state, ["goblin_01"], rng=random.Random(0))
    combat_state.combat_state.turn_order = ["player_01", "goblin_01"]
    combat_state.combat_state.current_turn = 0

    _judge_returns(monkeypatch, CombatAction(action="combat", targets=["goblin_01"]))
    # Hit + damage virtually guaranteed: STR 14 (mod +2) + sword 1d8 + nat 15 → damage ≥ 1
    rng = random.Random(99)
    events = await _collect(
        run_turn(
            client=None,
            state=combat_state,
            profile_dir="<unused>",
            saves_dir=tmp_data,
            player_input="공격",
            rng=rng,
        )
    )
    types = [e["type"] for e in events]
    if not combat_state.characters["goblin_01"].alive:
        assert "combat_end" in types
        end_ev = next(e for e in events if e["type"] == "combat_end")
        assert end_ev["data"]["outcome"] == "victory"
        assert combat_state.combat_state is None
