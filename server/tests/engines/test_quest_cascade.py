"""Tests for entity-death → quest fail/success cascade in check_quests."""

from src.domain.entities import (
    Character,
    Quest,
    QuestRewards,
    QuestTrigger,
    Stats,
)
from src.engines import quest as q


def _player():
    return Character(
        id="player_01",
        name="주",
        race_id="human",
        is_player=True,
        stats=Stats(),
        gold=0,
        xp_pool=0,
    )


def _quest(qid, *, giver_id="npc_giver", triggers=None, fail_triggers=None, status="active", rewards=None):
    return Quest(
        id=qid,
        title=qid,
        giver_id=giver_id,
        difficulty="보통",
        triggers=triggers or [],
        fail_triggers=fail_triggers or [],
        status=status,
        rewards=rewards or QuestRewards(),
    )


def _kill_trig(tid, target):
    return QuestTrigger(id=tid, name="kill", type="character_death", target_id=target)


def _state(fresh_state, *, quests=None, extra_chars=None):
    fresh_state.characters["player_01"] = _player()
    if quests:
        for quest_obj in quests:
            fresh_state.quests[quest_obj.id] = quest_obj
    if extra_chars:
        for char in extra_chars:
            fresh_state.characters[char.id] = char
    return fresh_state


def _npc(npc_id):
    return Character(id=npc_id, name=npc_id, race_id="human", stats=Stats())


# --- Giver death → quest fails --------------------------------------------


def test_giver_death_fails_active_quest(fresh_state):
    state = _state(
        fresh_state,
        quests=[_quest("q1", giver_id="edric_01")],
        extra_chars=[_npc("edric_01")],
    )
    dirty: set[tuple[str, str]] = set()
    changed = q.check_quests(state, "character_death", "edric_01", dirty)
    assert "q1" in changed
    assert state.quests["q1"].status == "failed"
    assert state.quests["q1"].fail_reason == "giver_dead"
    assert ("quests", "q1") in dirty


def test_giver_death_multiple_quests_all_fail(fresh_state):
    state = _state(
        fresh_state,
        quests=[
            _quest("q1", giver_id="edric_01"),
            _quest("q2", giver_id="edric_01"),
        ],
        extra_chars=[_npc("edric_01")],
    )
    q.check_quests(state, "character_death", "edric_01")
    assert state.quests["q1"].status == "failed"
    assert state.quests["q2"].status == "failed"
    assert state.quests["q1"].fail_reason == "giver_dead"
    assert state.quests["q2"].fail_reason == "giver_dead"


# --- Objective kill → quest completes -------------------------------------


def test_kill_target_death_completes_quest(fresh_state):
    state = _state(
        fresh_state,
        quests=[
            _quest(
                "q1",
                giver_id="guard_01",
                triggers=[_kill_trig("t1", "bandit_01")],
            )
        ],
        extra_chars=[_npc("guard_01"), _npc("bandit_01")],
    )
    dirty: set[tuple[str, str]] = set()
    changed = q.check_quests(state, "character_death", "bandit_01", dirty)
    assert "q1" in changed
    assert state.quests["q1"].status == "completed"
    assert state.quests["q1"].success_reason == "objective_killed"
    assert ("quests", "q1") in dirty


def test_kill_target_death_no_rewards_already_handled_by_trigger_path(fresh_state):
    """The cascade completes the quest via the normal trigger path when trigger fires."""
    state = _state(
        fresh_state,
        quests=[
            _quest(
                "q1",
                giver_id="guard_01",
                triggers=[_kill_trig("t1", "bandit_01")],
                rewards=QuestRewards(gold=50),
            )
        ],
        extra_chars=[_npc("guard_01"), _npc("bandit_01")],
    )
    q.check_quests(state, "character_death", "bandit_01")
    assert state.quests["q1"].status == "completed"
    assert state.characters["player_01"].gold == 50


# --- Unrelated entity death → no change -----------------------------------


def test_unrelated_death_does_not_change_quest(fresh_state):
    state = _state(
        fresh_state,
        quests=[_quest("q1", giver_id="edric_01")],
        extra_chars=[_npc("edric_01"), _npc("stranger_99")],
    )
    q.check_quests(state, "character_death", "stranger_99")
    assert state.quests["q1"].status == "active"


# --- Idempotency ----------------------------------------------------------


def test_already_failed_quest_stays_failed(fresh_state):
    state = _state(
        fresh_state,
        quests=[_quest("q1", giver_id="edric_01", status="failed")],
        extra_chars=[_npc("edric_01")],
    )
    changed = q.check_quests(state, "character_death", "edric_01")
    assert "q1" not in changed
    assert state.quests["q1"].status == "failed"


def test_already_completed_quest_stays_completed(fresh_state):
    state = _state(
        fresh_state,
        quests=[
            _quest(
                "q1",
                giver_id="guard_01",
                triggers=[_kill_trig("t1", "bandit_01")],
                status="completed",
            )
        ],
        extra_chars=[_npc("guard_01"), _npc("bandit_01")],
    )
    changed = q.check_quests(state, "character_death", "bandit_01")
    assert "q1" not in changed
    assert state.quests["q1"].status == "completed"


# --- Pending/locked quests unaffected -------------------------------------


def test_locked_quest_not_affected_by_giver_death(fresh_state):
    state = _state(
        fresh_state,
        quests=[_quest("q1", giver_id="edric_01", status="locked")],
        extra_chars=[_npc("edric_01")],
    )
    q.check_quests(state, "character_death", "edric_01")
    assert state.quests["q1"].status == "locked"


# --- Giver is also kill target: fail wins ---------------------------------


def test_giver_death_beats_kill_target_when_same_entity(fresh_state):
    """If the giver is also a kill-target trigger, fail_reason wins because fail
    triggers are evaluated first in the cascade."""
    state = _state(
        fresh_state,
        quests=[
            _quest(
                "q1",
                giver_id="edric_01",
                triggers=[_kill_trig("t1", "edric_01")],
            )
        ],
        extra_chars=[_npc("edric_01")],
    )
    q.check_quests(state, "character_death", "edric_01")
    assert state.quests["q1"].status == "failed"
    assert state.quests["q1"].fail_reason == "giver_dead"
