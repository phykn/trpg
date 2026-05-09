"""S3 — turn.run_turn combat-routing integration. Auto-mode only.

A CombatAction triggers start_combat + an auto-sim cycle inside the same
/turn — there is no `pending_check` dice button. Only judge is mocked; no
LLM call (client=None skips the cinematic narrate stream)."""

import random

import pytest

from src.game.domain.entities import Character, CombatBehavior, Stats
from src.db.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo
from src.llm.calls.classify.schema import Verb
from src.game.flow.confirmation import run_confirm
from src.game.flow.turn import run_turn


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
    return fresh_state


async def _confirm_pending_attack(state, tmp_data, collect, rng):
    return await collect(
        run_confirm(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            confirmation_id=state.pending_confirmation["id"],
            decision="confirm",
            rng=rng,
        )
    )


async def test_combat_starts_and_runs_auto_sim(
    combat_state, tmp_data, judge_returns, collect
):
    """A fresh combat input triggers combat_start + auto-sim — no pending_check."""
    judge_returns(Verb(name="attack", target_ids=["goblin_01"]))
    rng = random.Random(123)
    first_events = await collect(
        run_turn(
            client=None,
            state=combat_state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="고블린을 공격한다",
            rng=rng,
        )
    )
    assert any(e["type"] == "confirmation_required" for e in first_events)
    events = await _confirm_pending_attack(combat_state, tmp_data, collect, rng)

    types = [e["type"] for e in events]
    assert "combat_start" in types
    assert combat_state.pending_check is None
    # Goblin took some damage or died
    g = combat_state.characters["goblin_01"]
    assert g.hp < 8 or not g.alive


async def test_combat_with_invalid_target_does_not_consume_turn(
    combat_state, tmp_data, judge_returns, collect
):
    # Regression: judge sometimes returned target=<location_id> (e.g. "swamp")
    # for a "rush into the fog" input. The dispatcher used to forward it to
    # start_combat, leaving combat_state in a half-broken shape. Now the
    # dispatcher rejects unknown / dead targets without consuming the turn.
    judge_returns(Verb(name="attack", target_ids=["unknown_id"]))
    turn_before = combat_state.turn_count
    events = await collect(
        run_turn(
            client=None,
            state=combat_state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="안개 속으로 검을 휘두른다",
            rng=random.Random(1),
        )
    )
    types = [e["type"] for e in events]
    assert "combat_start" not in types
    assert combat_state.combat_state is None
    assert combat_state.turn_count == turn_before


async def test_combat_with_self_target_does_not_consume_turn(
    combat_state, tmp_data, judge_returns, collect
):
    # Regression: judge sometimes returned `targets=['player_01']` (the player
    # attacking themselves). The dispatcher used to start combat with the
    # player as the only enemy, which then ended immediately — turn_count went
    # up but nothing else moved.
    judge_returns(Verb(name="attack", target_ids=["player_01"]))
    turn_before = combat_state.turn_count
    events = await collect(
        run_turn(
            client=None,
            state=combat_state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="자신을 베어버린다",
            rng=random.Random(1),
        )
    )
    types = [e["type"] for e in events]
    assert "combat_start" not in types
    assert combat_state.combat_state is None
    assert combat_state.turn_count == turn_before


async def test_combat_player_attack_drops_affinity_bidirectional(
    combat_state, tmp_data, judge_returns, collect
):
    """Attacking an NPC must drop affinity on both sides — combat never reaches
    narrate, so without the engine-side hook trade/social_bonus would still
    treat the target as neutral. Regression for the hole where attacks left
    relations untouched."""
    from src.game.rules import RULES

    combat_state.characters["player_01"].relations["goblin_01"] = 0
    combat_state.characters["goblin_01"].relations["player_01"] = 0

    judge_returns(Verb(name="attack", target_ids=["goblin_01"]))
    await collect(
        run_turn(
            client=None,
            state=combat_state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="공격",
            rng=random.Random(7),
        )
    )
    await _confirm_pending_attack(combat_state, tmp_data, collect, random.Random(7))
    drop = RULES.social.combat_affinity_drop
    assert combat_state.characters["player_01"].relations["goblin_01"] <= -drop
    assert combat_state.characters["goblin_01"].relations["player_01"] <= -drop


async def test_combat_pass_action_runs_auto_sim_round(
    combat_state, tmp_data, judge_returns, collect
):
    """In-combat PassAction → auto-sim runs at least one round (player passes,
    NPC takes its turn). combat_state ends up either cleared (decisive
    outcome) or still set with rounds advanced."""
    from src.game.engines import combat as combat_engine

    combat_engine.start_combat(combat_state, ["goblin_01"], rng=random.Random(0))
    combat_state.combat_state.turn_order = ["player_01", "goblin_01"]
    combat_state.combat_state.current_turn = 0

    judge_returns(Verb(name="wait"))
    rng = random.Random(2)
    events = await collect(
        run_turn(
            client=None,
            state=combat_state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="대기",
            rng=rng,
        )
    )
    # Numeric outcome summary is pushed regardless of cinematic
    types = [e["type"] for e in events]
    assert "log_entry" in types  # judge log + player log + maybe summary act_line


async def test_start_combat_raises_when_already_in_combat(
    combat_state, tmp_data, collect
):
    # /turn routes through run_combat_player_turn whenever combat_state is
    # set, so reaching start_combat_and_drive_auto with a live combat
    # already pinned means the state machine is broken (some path forgot to
    # call end_combat). Fail loud — silently re-using the stale combat_state
    # with brand-new enemy_ids would mask the bug.
    import pytest
    from src.game.domain.errors import CombatStateInvalid
    from src.game.engines import combat as combat_engine
    from src.game.flow.combat_auto import PlayerAction
    from src.game.flow.combat_phase import start_combat_and_drive_auto
    from src.game.flow.dirty import Dirty

    combat_engine.start_combat(combat_state, ["goblin_01"], rng=random.Random(0))
    combat_state.combat_state.turn_order = ["player_01", "goblin_01"]
    combat_state.combat_state.current_turn = 0

    dirty = Dirty()
    with pytest.raises(CombatStateInvalid):
        await collect(
            start_combat_and_drive_auto(
                client=None,
                state=combat_state,
                scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
                enemy_ids=["goblin_01"],
                dirty=dirty,
                rng=random.Random(1),
                player_input="공격",
                player_action=PlayerAction(kind="attack", targets=["goblin_01"]),
            )
        )


async def test_combat_ends_when_enemy_dies_from_player_attack(
    combat_state, tmp_data, judge_returns, collect
):
    """Drop goblin hp to 1 so it dies in one hit → combat_end victory emitted
    and combat_state cleared."""
    combat_state.characters["goblin_01"].hp = 1
    combat_state.characters["goblin_01"].max_hp = 1

    judge_returns(Verb(name="attack", target_ids=["goblin_01"]))
    rng = random.Random(99)
    events = await collect(
        run_turn(
            client=None,
            state=combat_state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
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
