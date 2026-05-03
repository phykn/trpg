"""Pending → active (accept) → abandoned (abandon) state transitions."""

from src.domain.entities import Character, Quest, QuestRewards, Stats
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


def _quest(qid, *, giver_id="npc_giver", status="active", requires_acceptance=False):
    return Quest(
        id=qid,
        title=qid,
        giver_id=giver_id,
        difficulty="보통",
        status=status,
        requires_acceptance=requires_acceptance,
        rewards=QuestRewards(),
    )


def _state(fresh_state, *, quests=None):
    fresh_state.characters["player_01"] = _player()
    if quests:
        for quest_obj in quests:
            fresh_state.quests[quest_obj.id] = quest_obj
    return fresh_state


# --- accept_quest -----------------------------------------------------------


def test_pending_quest_accepts_to_active(fresh_state):
    """Quest with requires_acceptance=True starts pending, accept transitions to active."""
    state = _state(
        fresh_state, quests=[_quest("q1", status="pending", requires_acceptance=True)]
    )
    assert state.quests["q1"].status == "pending"
    result = q.accept_quest(state, "q1")
    assert result is True
    assert state.quests["q1"].status == "active"


def test_cannot_accept_completed_quest(fresh_state):
    """Completed quest is immune to accept_quest (idempotent)."""
    state = _state(fresh_state, quests=[_quest("q1", status="completed")])
    q.accept_quest(state, "q1")
    assert state.quests["q1"].status == "completed"


def test_cannot_accept_active_quest(fresh_state):
    """Already-active quest is not changed by accept_quest."""
    state = _state(fresh_state, quests=[_quest("q1", status="active")])
    result = q.accept_quest(state, "q1")
    assert result is False
    assert state.quests["q1"].status == "active"


def test_accept_nonexistent_quest_returns_false(fresh_state):
    state = _state(fresh_state)
    result = q.accept_quest(state, "no_such_quest")
    assert result is False


# --- abandon_quest ----------------------------------------------------------


def test_active_quest_abandons(fresh_state):
    """Active quest → failed via explicit player action ('의뢰 포기')."""
    state = _state(fresh_state, quests=[_quest("q1", status="active")])
    result = q.abandon_quest(state, "q1")
    assert result is True
    assert state.quests["q1"].status == "failed"
    assert state.quests["q1"].fail_reason == "의뢰 포기"


def test_abandon_quest_emits_fail_card(fresh_state):
    """abandon_quest with a full Dirty pushes the '의뢰 포기' fail card."""
    from src.flow.dirty import Dirty

    state = _state(fresh_state, quests=[_quest("q1", status="active")])
    state.quests["q1"].title = "촌장의 부탁"
    state.active_quest_id = "q1"
    dirty = Dirty()
    q.abandon_quest(state, "q1", dirty)
    assert state.quests["q1"].status == "failed"
    assert state.active_quest_id is None
    texts = [e.model_dump().get("text", "") for e in dirty.log]
    assert any("퀘스트 실패: 촌장의 부탁" in t and "의뢰 포기" in t for t in texts), texts


def test_cannot_abandon_pending_quest(fresh_state):
    """Pending → abandoned not allowed; only active can be abandoned."""
    state = _state(fresh_state, quests=[_quest("q1", status="pending")])
    result = q.abandon_quest(state, "q1")
    assert result is False
    assert state.quests["q1"].status == "pending"


def test_cannot_abandon_completed_quest(fresh_state):
    state = _state(fresh_state, quests=[_quest("q1", status="completed")])
    result = q.abandon_quest(state, "q1")
    assert result is False
    assert state.quests["q1"].status == "completed"


def test_abandon_nonexistent_quest_returns_false(fresh_state):
    state = _state(fresh_state)
    result = q.abandon_quest(state, "no_such_quest")
    assert result is False


# --- abandoned immunity to triggers -----------------------------------------


def test_failed_quest_immune_to_objective_check(fresh_state):
    """Already-failed quest stays failed even if objective target dies."""
    from src.domain.entities import QuestTrigger

    trigger = QuestTrigger(
        id="t1", name="kill goblin", type="character_death", target_id="goblin"
    )
    quest_obj = Quest(
        id="q1",
        title="q1",
        giver_id="npc_giver",
        difficulty="보통",
        status="failed",
        triggers=[trigger],
        rewards=QuestRewards(),
    )
    state = _state(fresh_state, quests=[quest_obj])
    dirty: set[tuple[str, str]] = set()
    q.check_quests(state, "character_death", "goblin", dirty)
    assert state.quests["q1"].status == "failed"


def test_failed_quest_immune_to_giver_death(fresh_state):
    """Failed quest is not re-failed when giver dies."""
    quest_obj = Quest(
        id="q1",
        title="q1",
        giver_id="npc_giver",
        difficulty="보통",
        status="failed",
        fail_reason="의뢰 포기",
        rewards=QuestRewards(),
    )
    npc = Character(id="npc_giver", name="npc_giver", race_id="human", stats=Stats())
    state = _state(fresh_state, quests=[quest_obj])
    state.characters["npc_giver"] = npc
    dirty: set[tuple[str, str]] = set()
    changed = q.check_quests(state, "character_death", "npc_giver", dirty)
    assert "q1" not in changed
    assert state.quests["q1"].status == "failed"
    assert state.quests["q1"].fail_reason == "의뢰 포기"


# --- pending immunity to triggers -------------------------------------------


def test_pending_quest_fails_on_giver_death(fresh_state):
    """Pending quest (offered but not yet accepted) becomes unrecoverable when
    giver dies — the player can no longer accept, so it must close as failed."""
    quest_obj = Quest(
        id="q1",
        title="q1",
        giver_id="npc_giver",
        difficulty="보통",
        status="pending",
        rewards=QuestRewards(),
    )
    npc = Character(id="npc_giver", name="npc_giver", race_id="human", stats=Stats())
    state = _state(fresh_state, quests=[quest_obj])
    state.characters["npc_giver"] = npc
    changed = q.check_quests(state, "character_death", "npc_giver")
    assert "q1" in changed
    assert state.quests["q1"].status == "failed"
    assert state.quests["q1"].fail_reason == "의뢰자 사망"


# --- prerequisite unlock with requires_acceptance ---------------------


def test_unlocked_quest_with_requires_acceptance_goes_to_pending(fresh_state):
    """When a locked quest's prereq is met, it transitions to pending if requires_acceptance=True."""
    # q0 is a simple active quest we'll complete
    # q1 is locked with requires_acceptance=True, has q0 as prerequisite
    q0 = _quest("q0", status="active")
    q1 = _quest(
        "q1",
        status="locked",
        requires_acceptance=True,
    )
    q1.prerequisite_ids = ["q0"]

    state = _state(fresh_state, quests=[q0, q1])
    dirty: set[tuple[str, str]] = set()

    # Simulate q0 completion via check_quests
    # (this is how it normally happens: trigger fires, q0 → completed, then _maybe_unlock_dependents runs)
    q0.status = "completed"
    q.update_chapter_progress(state, dirty)
    q._maybe_unlock_dependents(state, dirty)

    # q1 should now be pending (awaiting accept_quest), not active
    assert state.quests["q1"].status == "pending"
    assert ("quests", "q1") in dirty


def test_unlocked_quest_without_requires_acceptance_goes_to_active(fresh_state):
    """When a locked quest's prereq is met, it transitions to active if requires_acceptance=False."""
    # q0 is a simple active quest we'll complete
    # q1 is locked with requires_acceptance=False, has q0 as prerequisite
    q0 = _quest("q0", status="active")
    q1 = _quest(
        "q1",
        status="locked",
        requires_acceptance=False,
    )
    q1.prerequisite_ids = ["q0"]

    state = _state(fresh_state, quests=[q0, q1])
    dirty: set[tuple[str, str]] = set()

    # Simulate q0 completion
    q0.status = "completed"
    q.update_chapter_progress(state, dirty)
    q._maybe_unlock_dependents(state, dirty)

    # q1 should now be active (auto-starts), not pending
    assert state.quests["q1"].status == "active"
    assert ("quests", "q1") in dirty
