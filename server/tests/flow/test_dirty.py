"""register_kill cascades giver death so any future kill path automatically closes orphaned quests."""

from src.domain.entities import Character, Quest, QuestRewards, Stats
from src.flow.dirty import Dirty, register_kill


def _player():
    return Character(
        id="player_01",
        name="주",
        race_id="human",
        is_player=True,
        stats=Stats(),
    )


def _npc(npc_id, name=None):
    return Character(id=npc_id, name=name or npc_id, race_id="human", stats=Stats())


def _active_quest(qid, *, giver_id, title):
    return Quest(
        id=qid,
        title=title,
        giver_id=giver_id,
        difficulty="normal",
        status="active",
        rewards=QuestRewards(),
    )


def test_register_kill_cascades_giver_death(fresh_state):
    """Live-test regression: killing the quest giver must close the orphaned quest.
    The cascade lives in register_kill so every kill path inherits it for free."""
    fresh_state.characters["player_01"] = _player()
    fresh_state.characters["edrik_01"] = _npc("edrik_01", "에드릭")
    quest = _active_quest("q_villager", giver_id="edrik_01", title="촌장의 부탁")
    fresh_state.quests[quest.id] = quest
    fresh_state.active_quest_id = quest.id

    dirty = Dirty()
    register_kill(fresh_state, "edrik_01", dirty)

    assert fresh_state.quests["q_villager"].status == "failed"
    assert fresh_state.quests["q_villager"].fail_reason == "의뢰자 사망"
    assert fresh_state.active_quest_id is None
    texts = [text for text, _ in dirty.deferred_act_cards]
    assert any("퀘스트 실패: 촌장의 부탁" in t and "의뢰자 사망" in t for t in texts), (
        texts
    )


def test_register_kill_no_quest_giver_match_is_noop(fresh_state):
    """Killing an NPC who isn't a giver leaves quests untouched."""
    fresh_state.characters["player_01"] = _player()
    fresh_state.characters["bandit_01"] = _npc("bandit_01", "약탈자")
    quest = _active_quest("q_villager", giver_id="edrik_01", title="촌장의 부탁")
    fresh_state.quests[quest.id] = quest

    dirty = Dirty()
    register_kill(fresh_state, "bandit_01", dirty)

    assert fresh_state.quests["q_villager"].status == "active"


def test_register_kill_still_pushes_death_turn_log(fresh_state):
    """The original turn_log push must keep firing alongside the new cascade."""
    fresh_state.characters["player_01"] = _player()
    fresh_state.characters["bandit_01"] = _npc("bandit_01", "약탈자")

    dirty = Dirty()
    register_kill(fresh_state, "bandit_01", dirty)

    assert any("약탈자 사망" in e.summary for e in dirty.history)
    assert ("characters", "bandit_01") in dirty.entities
