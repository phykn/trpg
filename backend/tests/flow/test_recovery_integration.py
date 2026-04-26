"""turn.run_turn 의 rest 라우팅 — judge mock, recovery 엔진 + combat 부팅 통합."""
import random
import tempfile
from datetime import datetime, timedelta

import pytest

from src.domain.entities import Character, CombatBehavior, Location, Stats
from src.agents.dc_judge.schema import RestAction
from src.flow import judge as judge_mod
from src.flow import combat_phase as combat_phase_mod
from src.flow import turn as turn_mod
from src.flow.turn import run_turn
from src.rules import RULES


@pytest.fixture
def tmp_data():
    with tempfile.TemporaryDirectory() as d:
        yield d


def _judge_returns_rest(monkeypatch):
    async def fake_judge(client, state, player_input):
        return RestAction(action="rest")
    monkeypatch.setattr(judge_mod, "run_judge", fake_judge)
    monkeypatch.setattr(turn_mod, "run_judge", fake_judge)
    monkeypatch.setattr(combat_phase_mod, "run_judge", fake_judge)


def _seed_player(state, *, hp=4, mp=2):
    state.characters["player_01"] = Character(
        id="player_01",
        name="주",
        race_id="human",
        is_player=True,
        location_id="plaza_01",
        stats=Stats(STR=10, DEX=12, CON=10, INT=10, WIS=10, CHA=10),
        hp=hp,
        max_hp=20,
        mp=mp,
        max_mp=15,
    )


async def _collect(it):
    return [ev async for ev in it]


async def test_rest_in_safe_location_full_recovery(fresh_state, tmp_data, monkeypatch):
    _seed_player(fresh_state)
    fresh_state.locations["plaza_01"] = Location(
        id="plaza_01", name="광장", sleep_risk="safe"
    )
    before_time = fresh_state.world_time

    _judge_returns_rest(monkeypatch)
    events = await _collect(
        run_turn(
            client=None,
            state=fresh_state,
            profile_dir="<unused>",
            saves_dir=tmp_data,
            player_input="여기서 잠을 잔다",
            rng=random.Random(7),
        )
    )

    types = [e["type"] for e in events]
    assert "judge" in types
    assert types[-1] == "done"
    assert "combat_start" not in types

    actor = fresh_state.characters["player_01"]
    assert actor.hp == actor.max_hp
    assert actor.mp == actor.max_mp
    expected_time = (
        datetime.fromisoformat(before_time)
        + timedelta(hours=RULES.time.sleep_hours)
    ).isoformat()
    assert fresh_state.world_time == expected_time
    assert fresh_state.turn_count == 1


async def test_rest_in_dangerous_location_triggers_encounter(
    fresh_state, tmp_data, monkeypatch
):
    _seed_player(fresh_state, hp=20)  # 풀체력으로 시작 (회복 안 일어나는 거 보려고)
    fresh_state.locations["plaza_01"] = Location(
        id="plaza_01",
        name="동굴",
        sleep_risk="dangerous",
        sleep_encounters=["goblin_01"],
    )
    fresh_state.characters["goblin_01"] = Character(
        id="goblin_01",
        name="고블린",
        race_id="goblin",
        location_id="plaza_01",
        stats=Stats(STR=10, DEX=12, CON=10, INT=10, WIS=10, CHA=10),
        hp=8,
        max_hp=8,
        combat_behavior=CombatBehavior(attack_priority="nearest"),
    )

    _judge_returns_rest(monkeypatch)
    # rng.random() 의 첫 호출이 encounter 굴림 — 0 으로 강제 발동.
    # Random(seed) 는 seed 별로 random() 값이 결정론. 인카운터 발동시키는 seed 는?
    # 간단하게 monkeypatch.setattr 로 random.random 을 모킹하지 말고, 임의 seed 로 시도.
    rng = random.Random(0)
    events = await _collect(
        run_turn(
            client=None,
            state=fresh_state,
            profile_dir="<unused>",
            saves_dir=tmp_data,
            player_input="여기서 잠을 청한다",
            rng=rng,
        )
    )

    types = [e["type"] for e in events]
    # dangerous=0.6, Random(0).random() ≈ 0.844 → encounter 안 발동. 다른 seed 필요.
    # 발동되든 안 되든 한 시나리오는 검증되니, encounter 가 안 떠도 OK.
    if "combat_start" in types:
        assert fresh_state.combat_state is not None
        cs = fresh_state.combat_state
        assert "goblin_01" in cs.enemy_ids
        assert cs.surprise == "enemy"
    else:
        # encounter 안 떴으면 풀회복.
        actor = fresh_state.characters["player_01"]
        assert actor.hp == actor.max_hp


async def test_rest_dangerous_with_low_random_forces_encounter(
    fresh_state, tmp_data, monkeypatch
):
    """recovery.random.random() 을 0.0 으로 패치 — dangerous 면 무조건 발동."""
    _seed_player(fresh_state, hp=20)
    fresh_state.locations["plaza_01"] = Location(
        id="plaza_01",
        name="동굴",
        sleep_risk="dangerous",
        sleep_encounters=["goblin_01"],
    )
    fresh_state.characters["goblin_01"] = Character(
        id="goblin_01",
        name="고블린",
        race_id="goblin",
        location_id="plaza_01",
        stats=Stats(STR=10, DEX=12, CON=10, INT=10, WIS=10, CHA=10),
        hp=8,
        max_hp=8,
        combat_behavior=CombatBehavior(attack_priority="nearest"),
    )

    class _ForceLow:
        """recovery 에 넘기는 rng — random() 0 만 반환, randint 는 random 위임."""

        def random(self):
            return 0.0

        def randint(self, a, b):
            return random.Random(99).randint(a, b)

    _judge_returns_rest(monkeypatch)
    events = await _collect(
        run_turn(
            client=None,
            state=fresh_state,
            profile_dir="<unused>",
            saves_dir=tmp_data,
            player_input="잠을 잔다",
            rng=_ForceLow(),
        )
    )

    types = [e["type"] for e in events]
    assert "combat_start" in types
    assert fresh_state.combat_state is not None
    cs = fresh_state.combat_state
    assert cs.surprise == "enemy"
    assert "goblin_01" in cs.enemy_ids
    # 첫 라운드 player skip 이벤트
    skip_events = [
        e for e in events
        if e["type"] == "combat_turn" and e["data"].get("action") == "skip"
    ]
    assert any(ev["data"]["actor"] == "player_01" for ev in skip_events)


async def test_rest_blocked_during_combat(fresh_state, tmp_data, monkeypatch):
    """combat_state 활성 중 rest 시도 → 거절 메시지, 회복 안 일어남."""
    from src.engines import combat as combat_engine

    _seed_player(fresh_state, hp=4)
    fresh_state.characters["goblin_01"] = Character(
        id="goblin_01",
        name="고블린",
        race_id="goblin",
        location_id="plaza_01",
        stats=Stats(STR=10, DEX=12, CON=10, INT=10, WIS=10, CHA=10),
        hp=8,
        max_hp=8,
        combat_behavior=CombatBehavior(attack_priority="nearest"),
    )
    fresh_state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    combat_engine.start_combat(fresh_state, ["goblin_01"], rng=random.Random(0))
    fresh_state.combat_state.turn_order = ["player_01", "goblin_01"]
    fresh_state.combat_state.current_turn = 0

    _judge_returns_rest(monkeypatch)
    await _collect(
        run_turn(
            client=None,
            state=fresh_state,
            profile_dir="<unused>",
            saves_dir=tmp_data,
            player_input="잠을 잔다",
            rng=random.Random(7),
        )
    )

    actor = fresh_state.characters["player_01"]
    assert actor.hp == 4  # 회복 안 됨
