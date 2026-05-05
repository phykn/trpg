"""recovery.attempt_rest — deterministic tests for the full-recovery / encounter branch."""

from src.game.domain.clock import next_dawn_turn
from src.game.domain.entities import Character, Location, Stats
from src.game.engines import recovery


class _SeqRandom:
    """random.Random stand-in — returns the supplied random() values in order."""

    def __init__(self, sequence):
        self._seq = list(sequence)
        self._i = 0

    def random(self) -> float:
        v = self._seq[self._i]
        self._i += 1
        return v

    def randint(self, a, b):
        # Not used by the encounter roll, but kept for other call sites.
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
        gold=100,
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
    before_turn = state.turn_count

    outcome, enemies = await recovery.attempt_rest(
        state, "player_01", rng=_SeqRandom([0.99]), dirty=set()
    )

    assert outcome == "full_recovery"
    assert enemies == []
    actor = state.characters["player_01"]
    assert actor.hp == actor.max_hp
    assert actor.mp == actor.max_mp
    # turn_count jumps to next dawn boundary
    assert state.turn_count == next_dawn_turn(before_turn)


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
    before_turn = state.turn_count

    # encounter_chance dangerous=0.6, rng.random()=0.1 → triggers
    outcome, enemies = await recovery.attempt_rest(
        state, "player_01", rng=_SeqRandom([0.1]), dirty=set()
    )

    assert outcome == "encounter"
    assert enemies == ["goblin_01"]
    # No healing, no turn advance (combat handles its own clock)
    assert state.characters["player_01"].hp == before_hp
    assert state.turn_count == before_turn


async def test_dangerous_without_encounter_falls_through_to_recovery(fresh_state):
    """encounter_chance > 0 but random() above threshold → full recovery."""
    state = _seed_state(fresh_state, risk="dangerous", encounters=["goblin_01"])

    # 0.99 > 0.6 → no encounter, full recovery
    outcome, enemies = await recovery.attempt_rest(
        state, "player_01", rng=_SeqRandom([0.99]), dirty=set()
    )

    assert outcome == "full_recovery"
    assert enemies == []
    actor = state.characters["player_01"]
    assert actor.hp == actor.max_hp


async def test_risky_with_empty_pool_falls_back_to_recovery(fresh_state):
    """Risk roll triggers but sleep_encounters pool is empty → fall back to full recovery."""
    state = _seed_state(fresh_state, risk="risky", encounters=[])

    # rng=0.0 (always triggers) → empty pool falls through to full recovery
    outcome, enemies = await recovery.attempt_rest(
        state, "player_01", rng=_SeqRandom([0.0]), dirty=set()
    )

    assert outcome == "full_recovery"
    assert enemies == []


async def test_dead_enemy_is_filtered_from_pool(fresh_state):
    """If a character in sleep_encounters is dead, drop them from the pool and fall back."""
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
    """A character with no location_id has no known risk, so they full-recover."""
    actor = Character(
        id="player_01",
        name="주",
        race_id="human",
        is_player=True,
        location_id=None,
        stats=Stats(),
        gold=100,
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
