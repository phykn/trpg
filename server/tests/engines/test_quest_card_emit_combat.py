"""When a kill in combat completes a quest, _apply_rewards must push the
'퀘스트 성공: ...' act entry to dirty.log AND state.log_entries. Live UX
report (2026-05-04): rewards land but the success card is missing from
the chat — covers that path so the regression can't recur."""

from src.domain.entities import (
    Character,
    CombatBehavior,
    Location,
    Quest,
    QuestRewards,
    QuestTrigger,
    Race,
    Stats,
)
from src.domain.state import GameState
from src.engines.combat import apply_attack_to_defender
from src.flow.dirty import Dirty


def _build() -> tuple[GameState, Dirty]:
    state = GameState(game_id="t", profile="test", player_id="player_01")
    state.locations["mountain_road"] = Location(
        id="mountain_road",
        name="산문 길",
        description="",
        connections=[],
    )
    state.races["human"] = Race(id="human", name="인간", description="")
    state.races["goblin"] = Race(id="goblin", name="고블린", description="")
    state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        stats=Stats(),
        location_id="mountain_road",
        gold=0,
        xp_pool=0,
    )
    state.characters["enemy_01"] = Character(
        id="enemy_01",
        name="고블린 약탈자",
        race_id="goblin",
        stats=Stats(),
        location_id="mountain_road",
        combat_behavior=CombatBehavior(),
        hp=10,
        max_hp=10,
    )
    state.quests["q_chief_request"] = Quest(
        id="q_chief_request",
        title="촌장의 부탁",
        giver_id="edrik",
        difficulty="쉬움",
        triggers=[
            QuestTrigger(
                id="t0",
                name="처치",
                type="character_death",
                target_id="enemy_01",
            )
        ],
        rewards=QuestRewards(exp=80, gold=40),
        status="active",
    )
    state.active_quest_id = "q_chief_request"
    state.invalidate_graph()
    return state, Dirty()


def test_combat_kill_completes_quest_and_stashes_success_card():
    """Reward + quest state must apply immediately. Success card text must be
    queued in dirty.deferred_act_cards so caller (combat_phase) can flush it
    AFTER 전투 결과 — not directly into log_entries here."""
    state, dirty = _build()
    apply_attack_to_defender(
        state,
        "enemy_01",
        damage=10,
        nat_d20=10,
        dirty=dirty,
        attacker_id="player_01",
    )
    # Reward applied immediately
    player = state.characters["player_01"]
    assert player.gold == 40
    assert player.xp_pool == 80
    assert state.quests["q_chief_request"].status == "completed"
    # Success card stashed for deferred flush — must NOT be in log_entries yet
    early_log_success = [
        e for e in state.log_entries if e.kind == "act" and "퀘스트 성공" in e.text
    ]
    assert not early_log_success, [(e.kind, e.text) for e in state.log_entries]
    # Should be in deferred queue
    assert dirty.deferred_act_cards, dirty.deferred_act_cards
    text, summary = dirty.deferred_act_cards[0]
    assert "퀘스트 성공" in text
    assert "촌장의 부탁" in text
    assert summary is not None and "촌장의 부탁" in summary
