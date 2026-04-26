"""recovery.attempt_rest — 풀회복/인카운터 분기 결정론 테스트."""
from datetime import datetime, timedelta

from src.domain.entities import Character, Location, Stats
from src.pipeline import recovery
from src.rules import RULES


class _SeqRandom:
    """random.Random 대체 — random() 결과를 순서대로 반환."""

    def __init__(self, sequence):
        self._seq = list(sequence)
        self._i = 0

    def random(self) -> float:
        v = self._seq[self._i]
        self._i += 1
        return v

    def randint(self, a, b):
        # encounter 굴림에는 안 쓰지만 다른 호출 대비.
        v = self._seq[self._i]
        self._i += 1
        return a + int(v * (b - a + 1))


def _seed_state(fresh_state, *, risk="safe", encounters=None):
    actor = Character(
        id="player_01",
        name="주",
        race_id="human",
        is_player=True,
        location_id="plaza_01",
        stats=Stats(),
        hp=4,
        max_hp=20,
        mp=2,
        max_mp=15,
    )
    fresh_state.characters["player_01"] = actor
    fresh_state.locations["plaza_01"] = Location(
        id="plaza_01",
        name="광장",
        sleep_risk=risk,
        sleep_encounters=encounters or [],
    )
    return fresh_state


async def test_full_recovery_in_safe_location(fresh_state):
    state = _seed_state(fresh_state, risk="safe")
    before = state.world_time

    outcome, enemies = await recovery.attempt_rest(
        state, "player_01", rng=_SeqRandom([0.99]), dirty=set()
    )

    assert outcome == "full_recovery"
    assert enemies == []
    actor = state.characters["player_01"]
    assert actor.hp == actor.max_hp
    assert actor.mp == actor.max_mp
    # world_time 이 sleep_hours 만큼 진행
    expected = (
        datetime.fromisoformat(before) + timedelta(hours=RULES.time.sleep_hours)
    ).isoformat()
    assert state.world_time == expected


async def test_dangerous_with_encounter_pool_triggers_combat_branch(fresh_state):
    enemy = Character(
        id="goblin_01",
        name="고블린",
        race_id="goblin",
        location_id="plaza_01",
        stats=Stats(),
        hp=8,
        max_hp=8,
    )
    fresh_state.characters["goblin_01"] = enemy
    state = _seed_state(fresh_state, risk="dangerous", encounters=["goblin_01"])
    before_hp = state.characters["player_01"].hp
    before_time = state.world_time

    # encounter_chance dangerous=0.6, rng.random()=0.1 → 발동
    outcome, enemies = await recovery.attempt_rest(
        state, "player_01", rng=_SeqRandom([0.1]), dirty=set()
    )

    assert outcome == "encounter"
    assert enemies == ["goblin_01"]
    # 회복 안 됨, 시간도 안 흐름 (combat 이 자체 가산)
    assert state.characters["player_01"].hp == before_hp
    assert state.world_time == before_time


async def test_dangerous_without_encounter_falls_through_to_recovery(fresh_state):
    """encounter_chance > 0 이지만 random() 이 임계 위 → 풀회복."""
    state = _seed_state(fresh_state, risk="dangerous", encounters=["goblin_01"])

    # 0.99 > 0.6 → 인카운터 안 발동, 풀회복
    outcome, enemies = await recovery.attempt_rest(
        state, "player_01", rng=_SeqRandom([0.99]), dirty=set()
    )

    assert outcome == "full_recovery"
    assert enemies == []
    actor = state.characters["player_01"]
    assert actor.hp == actor.max_hp


async def test_risky_with_empty_pool_falls_back_to_recovery(fresh_state):
    """위험도 굴림 발동했지만 sleep_encounters 풀이 비어 있으면 풀회복 fallback."""
    state = _seed_state(fresh_state, risk="risky", encounters=[])

    # rng=0.0 (어떤 임계든 발동) → 풀이 비어서 풀회복으로 떨어짐
    outcome, enemies = await recovery.attempt_rest(
        state, "player_01", rng=_SeqRandom([0.0]), dirty=set()
    )

    assert outcome == "full_recovery"
    assert enemies == []


async def test_dead_enemy_is_filtered_from_pool(fresh_state):
    """sleep_encounters 안 캐릭터가 죽어 있으면 풀에서 빼고 fallback."""
    dead = Character(
        id="goblin_01",
        name="고블린",
        race_id="goblin",
        location_id="plaza_01",
        stats=Stats(),
        hp=0,
        max_hp=8,
        alive=False,
    )
    fresh_state.characters["goblin_01"] = dead
    state = _seed_state(fresh_state, risk="dangerous", encounters=["goblin_01"])

    outcome, enemies = await recovery.attempt_rest(
        state, "player_01", rng=_SeqRandom([0.0]), dirty=set()
    )

    assert outcome == "full_recovery"
    assert enemies == []


async def test_dirty_set_marks_actor_on_recovery(fresh_state):
    state = _seed_state(fresh_state, risk="safe")
    dirty: set[tuple[str, str]] = set()

    await recovery.attempt_rest(state, "player_01", rng=_SeqRandom([0.5]), dirty=dirty)

    assert ("characters", "player_01") in dirty


async def test_no_location_falls_back_to_recovery(fresh_state):
    """location_id 없는 캐릭터는 위험도 알 수 없으니 풀회복."""
    actor = Character(
        id="player_01",
        name="주",
        race_id="human",
        is_player=True,
        location_id=None,
        stats=Stats(),
        hp=1,
        max_hp=20,
    )
    fresh_state.characters["player_01"] = actor

    outcome, enemies = await recovery.attempt_rest(
        fresh_state, "player_01", rng=_SeqRandom([0.01]), dirty=set()
    )

    assert outcome == "full_recovery"
    assert enemies == []
    assert fresh_state.characters["player_01"].hp == 20
