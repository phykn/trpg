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
    state = _state(fresh_state, quests=[_quest("q1", status="pending", requires_acceptance=True)])
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
    """Active quest → abandoned via explicit player action."""
    state = _state(fresh_state, quests=[_quest("q1", status="active")])
    result = q.abandon_quest(state, "q1")
    assert result is True
    assert state.quests["q1"].status == "abandoned"
    assert state.quests["q1"].fail_reason == "abandoned"


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


def test_abandoned_quest_immune_to_objective_check(fresh_state):
    """Already-abandoned quest stays abandoned even if objective target dies."""
    from src.domain.entities import QuestTrigger

    trigger = QuestTrigger(id="t1", name="kill goblin", type="character_death", target_id="goblin")
    quest_obj = Quest(
        id="q1",
        title="q1",
        giver_id="npc_giver",
        difficulty="보통",
        status="abandoned",
        triggers=[trigger],
        rewards=QuestRewards(),
    )
    state = _state(fresh_state, quests=[quest_obj])
    dirty: set[tuple[str, str]] = set()
    q.check_quests(state, "character_death", "goblin", dirty)
    assert state.quests["q1"].status == "abandoned"


def test_abandoned_quest_immune_to_giver_death(fresh_state):
    """Abandoned quest is not re-failed when giver dies."""
    from src.domain.entities import QuestTrigger

    quest_obj = Quest(
        id="q1",
        title="q1",
        giver_id="npc_giver",
        difficulty="보통",
        status="abandoned",
        fail_reason="abandoned",
        rewards=QuestRewards(),
    )
    npc = Character(id="npc_giver", name="npc_giver", race_id="human", stats=Stats())
    state = _state(fresh_state, quests=[quest_obj])
    state.characters["npc_giver"] = npc
    dirty: set[tuple[str, str]] = set()
    changed = q.check_quests(state, "character_death", "npc_giver", dirty)
    assert "q1" not in changed
    assert state.quests["q1"].status == "abandoned"
    assert state.quests["q1"].fail_reason == "abandoned"


# --- pending immunity to triggers -------------------------------------------


def test_pending_quest_immune_to_giver_death(fresh_state):
    """Pending quest (not yet accepted) is not failed when giver dies."""
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
    assert "q1" not in changed
    assert state.quests["q1"].status == "pending"
