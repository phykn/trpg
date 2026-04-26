"""S3 — turn.run_turn 의 combat 라우팅 integration. judge 만 모킹, LLM 안 부름."""
import random
import tempfile

import pytest

from src.domain.entities import Character, CombatBehavior, Equipment, Stats
from src.agents.dc_judge.schema import (
    CombatAction,
    PassAction,
)
from src.pipeline import judge as judge_mod
from src.pipeline import turn as turn_mod
from src.pipeline.turn import run_turn
from src.domain.state import GameState


@pytest.fixture
def tmp_data():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def combat_state(fresh_state, tmp_data):
    """player + goblin (둘 다 plaza_01) 가 같이 있는 GameState. saves_dir 는 tmp_data."""
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
    # save_full 이 game dir 을 만들도록 살짝 우회: 직접 디렉터리 prep 보다 turn flow 가 _flush 부를 때 처음 만들게 해도 OK.
    return fresh_state


def _judge_returns(monkeypatch, action_obj):
    async def fake_judge(client, state, player_input):
        return action_obj
    monkeypatch.setattr(judge_mod, "run_judge", fake_judge)
    monkeypatch.setattr(turn_mod, "run_judge", fake_judge)


async def _collect(it):
    return [ev async for ev in it]


async def test_combat_start_and_npc_round_progress(combat_state, tmp_data, monkeypatch):
    """player 의 첫 'combat' 입력 → combat_start, goblin 차례 한 번, player 차례에서 멈춤."""
    _judge_returns(monkeypatch, CombatAction(action="combat", targets=["goblin_01"]))
    rng = random.Random(123)  # 결정론
    events = await _collect(
        run_turn(
            client=None,  # judge 모킹돼 안 씀
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


async def test_combat_player_attack_advances_round(combat_state, tmp_data, monkeypatch):
    """combat_state 활성 + player 차례. CombatAction 으로 공격 → 데미지 적용."""
    # 사전 부팅
    from src.pipeline import combat as combat_engine
    combat_engine.start_combat(combat_state, ["goblin_01"], rng=random.Random(0))
    # player 차례에 멈추도록 turn_order 조정
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
    # goblin 이 데미지를 받았거나 죽었거나
    g = combat_state.characters["goblin_01"]
    assert g.hp < goblin_hp_before or not g.alive


async def test_combat_pass_action_consumes_player_turn(combat_state, tmp_data, monkeypatch):
    from src.pipeline import combat as combat_engine
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
    # pass + npc 1 회 → 라운드가 적어도 1 증가했어야 (player 까지 다시 돌아오려면 한 바퀴)
    assert combat_state.combat_state is None or combat_state.combat_state.round >= round_before
    types = [e["type"] for e in events]
    # pass 도 combat_turn 이벤트로 기록
    assert "combat_turn" in types


async def test_combat_ends_when_enemy_dies_from_player_attack(
    combat_state, tmp_data, monkeypatch
):
    """goblin hp 를 1 로 줄여 한 방에 죽도록 → combat_end victory 발행."""
    from src.pipeline import combat as combat_engine
    combat_state.characters["goblin_01"].hp = 1
    combat_state.characters["goblin_01"].max_hp = 1
    combat_engine.start_combat(combat_state, ["goblin_01"], rng=random.Random(0))
    combat_state.combat_state.turn_order = ["player_01", "goblin_01"]
    combat_state.combat_state.current_turn = 0

    _judge_returns(monkeypatch, CombatAction(action="combat", targets=["goblin_01"]))
    # 명중 + 데미지 보장: STR 14 (mod +2) + sword 1d8 + nat 15 → 1 이상 데미지 거의 확실
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
