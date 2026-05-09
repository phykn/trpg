"""Tests for entity-death → quest fail/success cascade in check_quests."""

from src.game.domain.entities import (
    Character,
    Quest,
    QuestRewards,
    QuestTrigger,
    Stats,
)
from src.game.engines import quest as q


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


def _quest(
    qid,
    *,
    giver_id="npc_giver",
    triggers=None,
    fail_triggers=None,
    status="active",
    rewards=None,
):
    return Quest(
        id=qid,
        title=qid,
        giver_id=giver_id,
        difficulty="normal",
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
    assert state.quests["q1"].fail_reason == "의뢰자 사망"
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
    assert state.quests["q1"].fail_reason == "의뢰자 사망"
    assert state.quests["q2"].fail_reason == "의뢰자 사망"


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
    assert state.quests["q1"].fail_reason == "의뢰자 사망"


# --- _fail_quest direct call ----------------------------------------------


def test_fail_quest_sets_status_and_clears_active(fresh_state):
    """_fail_quest with a full Dirty: status flips to failed, fail_reason set,
    fail card lands in dirty.log, active_quest_id clears when matching."""
    from src.game.flow.dirty import Dirty

    state = _state(
        fresh_state,
        quests=[_quest("q1", giver_id="edric_01")],
        extra_chars=[_npc("edric_01")],
    )
    state.quests["q1"].title = "촌장의 부탁"
    state.active_quest_id = "q1"
    dirty = Dirty()
    q._fail_quest(state, state.quests["q1"], reason="의뢰자 사망", dirty=dirty)
    assert state.quests["q1"].status == "failed"
    assert state.quests["q1"].fail_reason == "의뢰자 사망"
    assert state.active_quest_id is None
    texts = [text for text, _ in dirty.deferred_act_cards]
    assert any("퀘스트 실패: 촌장의 부탁" in t and "의뢰자 사망" in t for t in texts), (
        texts
    )


def test_fail_quest_keeps_active_pointer_when_other(fresh_state):
    from src.game.flow.dirty import Dirty

    state = _state(
        fresh_state,
        quests=[
            _quest("q1", giver_id="edric_01"),
            _quest("q2", giver_id="edric_01"),
        ],
        extra_chars=[_npc("edric_01")],
    )
    state.active_quest_id = "q2"
    q._fail_quest(state, state.quests["q1"], reason="의뢰자 사망", dirty=Dirty())
    assert state.active_quest_id == "q2"


# --- cascade_giver_death (called from register_kill) ----------------------


def test_cascade_giver_death_fails_active_quests_with_that_giver(fresh_state):
    """Multiple quests, only those with matching giver flip to failed."""
    from src.game.flow.dirty import Dirty

    state = _state(
        fresh_state,
        quests=[
            _quest("q1", giver_id="edric_01"),
            _quest("q2", giver_id="edric_01"),
            _quest("q3", giver_id="elder_05"),
        ],
        extra_chars=[_npc("edric_01"), _npc("elder_05")],
    )
    dirty = Dirty()
    q.cascade_giver_death(state, "edric_01", dirty)
    assert state.quests["q1"].status == "failed"
    assert state.quests["q2"].status == "failed"
    assert state.quests["q3"].status == "active"
    fail_texts = [text for text, _ in dirty.deferred_act_cards]
    assert sum("퀘스트 실패" in t for t in fail_texts) == 2


def test_cascade_giver_death_skips_completed_quests(fresh_state):
    """Quest already completed isn't reverted by cascade."""
    from src.game.flow.dirty import Dirty

    state = _state(
        fresh_state,
        quests=[_quest("q1", giver_id="edric_01", status="completed")],
        extra_chars=[_npc("edric_01")],
    )
    dirty = Dirty()
    q.cascade_giver_death(state, "edric_01", dirty)
    assert state.quests["q1"].status == "completed"
    assert dirty.log == []
    assert dirty.deferred_act_cards == []


def test_cascade_giver_death_with_set_dirty_skips_card_but_still_fails(fresh_state):
    """Back-compat: a bare entity-set as `dirty` mutates state but skips card emit."""
    state = _state(
        fresh_state,
        quests=[_quest("q1", giver_id="edric_01")],
        extra_chars=[_npc("edric_01")],
    )
    entities: set[tuple[str, str]] = set()
    q.cascade_giver_death(state, "edric_01", entities)
    assert state.quests["q1"].status == "failed"
    assert state.quests["q1"].fail_reason == "의뢰자 사망"
    assert ("quests", "q1") in entities
