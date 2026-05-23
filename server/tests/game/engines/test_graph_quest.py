import pytest

from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.graph.apply import apply_graph_change
from src.game.engines.graph.quest import (
    GraphQuestError,
    plan_quest_abandon,
    plan_quest_accept,
    plan_quest_complete,
    plan_quest_decide,
    plan_quest_fail,
    plan_quest_progress_for_trigger,
    plan_quest_progress_for_character_death,
    plan_quest_rewards,
)


def _graph() -> Graph:
    return Graph(
        nodes={
            "quest_pending": GraphNode(
                id="quest_pending",
                type="quest",
                properties={"status": "pending"},
            ),
            "quest_active": GraphNode(
                id="quest_active",
                type="quest",
                properties={"status": "active"},
            ),
            "quest_completed": GraphNode(
                id="quest_completed",
                type="quest",
                properties={"status": "completed"},
            ),
            "town": GraphNode(id="town", type="location"),
            "player_01": GraphNode(
                id="player_01",
                type="character",
                properties={"gold": 1, "xp_pool": 2},
            ),
            "goblin_01": GraphNode(
                id="goblin_01",
                type="character",
                properties={},
            ),
            "reward_sword": GraphNode(
                id="reward_sword",
                type="item",
                properties={"name": "보상 검"},
            ),
        }
    )


def _apply_all(graph: Graph, changes) -> Graph:
    for change in changes:
        graph = apply_graph_change(graph, change)
    return graph


def test_accept_pending_quest_sets_active():
    result = plan_quest_accept(_graph(), "quest_pending")
    changed = _apply_all(_graph(), result.changes)

    assert result.previous_status == "pending"
    assert result.next_status == "active"
    assert changed.nodes["quest_pending"].properties["status"] == "active"


def test_accept_pending_quest_rejects_when_another_quest_is_active():
    with pytest.raises(GraphQuestError, match="active quest already exists"):
        plan_quest_accept(
            _graph(),
            "quest_pending",
            active_quest_id="quest_active",
        )


def test_abandon_active_quest_sets_abandoned():
    result = plan_quest_abandon(_graph(), "quest_active")
    changed = _apply_all(_graph(), result.changes)

    assert result.previous_status == "active"
    assert result.next_status == "abandoned"
    assert changed.nodes["quest_active"].properties["status"] == "abandoned"


def test_complete_active_quest_sets_status_and_reason():
    result = plan_quest_complete(
        _graph(),
        "quest_active",
        reason="target cleared",
    )
    changed = _apply_all(_graph(), result.changes)

    assert result.next_status == "completed"
    assert changed.nodes["quest_active"].properties["status"] == "completed"
    assert changed.nodes["quest_active"].properties["success_reason"] == (
        "target cleared"
    )


def test_fail_active_quest_sets_status_and_reason():
    result = plan_quest_fail(_graph(), "quest_active", reason="target escaped")
    changed = _apply_all(_graph(), result.changes)

    assert result.next_status == "failed"
    assert changed.nodes["quest_active"].properties["status"] == "failed"
    assert changed.nodes["quest_active"].properties["fail_reason"] == "target escaped"


def test_character_death_trigger_completes_active_quest():
    graph = _graph()
    graph.nodes["quest_active"].properties.update(
        {
            "triggers": [
                {
                    "id": "trigger_01",
                    "name": "고블린 물리치기",
                    "type": "character_death",
                    "target": "goblin_01",
                }
            ],
            "triggers_met": [False],
        }
    )

    result = plan_quest_progress_for_character_death(graph, "goblin_01")
    changed = _apply_all(graph, result.changes)

    assert result.completed_quest_ids == ["quest_active"]
    assert changed.nodes["quest_active"].properties["triggers_met"] == [True]
    assert changed.nodes["quest_active"].properties["status"] == "completed"


def test_character_defeat_trigger_alias_completes_active_quest():
    graph = _graph()
    graph.nodes["quest_active"].properties.update(
        {
            "triggers": [
                {
                    "id": "trigger_01",
                    "name": "고블린 물리치기",
                    "type": "character_defeat",
                    "target": "goblin_01",
                }
            ],
            "triggers_met": [False],
        }
    )

    result = plan_quest_progress_for_character_death(graph, "goblin_01")
    changed = _apply_all(graph, result.changes)

    assert result.completed_quest_ids == ["quest_active"]
    assert changed.nodes["quest_active"].properties["status"] == "completed"


def test_location_enter_trigger_completes_accepted_pending_quest():
    graph = _graph()
    graph.nodes["quest_active"].properties.update(
        {
            "triggers": [
                {
                    "id": "trigger_01",
                    "name": "마을 도착",
                    "type": "location_enter",
                    "target": "town",
                }
            ],
            "triggers_met": [False],
        }
    )

    result = plan_quest_progress_for_trigger(graph, "location_enter", "town")
    changed = _apply_all(graph, result.changes)

    assert result.completed_quest_ids == ["quest_active"]
    assert changed.nodes["quest_active"].properties["triggers_met"] == [True]
    assert changed.nodes["quest_active"].properties["status"] == "completed"


def test_location_enter_trigger_does_not_complete_pending_quest_before_acceptance():
    graph = _graph()
    graph.nodes["quest_pending"].properties.update(
        {
            "triggers": [
                {
                    "id": "trigger_01",
                    "name": "마을 도착",
                    "type": "location_enter",
                    "target": "town",
                }
            ],
            "auto_complete_when_satisfied": True,
        }
    )

    result = plan_quest_progress_for_trigger(graph, "location_enter", "town")
    changed = _apply_all(graph, result.changes)

    assert result.completed_quest_ids == []
    assert changed.nodes["quest_pending"].properties.get("triggers_met") is None
    assert changed.nodes["quest_pending"].properties["status"] == "pending"


def test_location_enter_trigger_completes_active_quest():
    graph = _graph()
    graph.nodes["quest_pending"].properties.update(
        {
            "status": "active",
            "triggers": [
                {
                    "id": "trigger_01",
                    "name": "마을 도착",
                    "type": "location_enter",
                    "target": "town",
                }
            ],
            "auto_complete_when_satisfied": True,
        }
    )

    result = plan_quest_progress_for_trigger(graph, "location_enter", "town")
    changed = _apply_all(graph, result.changes)

    assert result.completed_quest_ids == ["quest_pending"]
    assert changed.nodes["quest_pending"].properties["triggers_met"] == [True]
    assert changed.nodes["quest_pending"].properties["status"] == "completed"


def test_trigger_progress_does_not_auto_complete_choice_quest():
    graph = _graph()
    graph.nodes["quest_active"].properties.update(
        {
            "triggers": [
                {
                    "id": "trigger_01",
                    "name": "마을 도착",
                    "type": "location_enter",
                    "target": "town",
                }
            ],
            "triggers_met": [False],
            "choices": {
                "record": {"label": "기록으로 남깁니다"},
                "release": {"label": "흘려보냅니다"},
            },
        }
    )

    result = plan_quest_progress_for_trigger(graph, "location_enter", "town")
    changed = _apply_all(graph, result.changes)

    assert result.completed_quest_ids == []
    assert changed.nodes["quest_active"].properties["triggers_met"] == [True]
    assert changed.nodes["quest_active"].properties["status"] == "active"


def test_decide_active_quest_sets_selected_choice_and_completes():
    graph = _graph()
    graph.nodes["quest_active"].properties["choices"] = {
        "record": {"label": "기록으로 남깁니다"},
        "release": {"label": "흘려보냅니다"},
    }

    result = plan_quest_decide(graph, "quest_active", "record")
    changed = _apply_all(graph, result.changes)

    assert result.action == "decide"
    assert result.next_status == "completed"
    assert changed.nodes["quest_active"].properties["selected_choice"] == "record"
    assert changed.nodes["quest_active"].properties["status"] == "completed"


def test_decide_rejects_before_required_triggers_are_met():
    graph = _graph()
    graph.nodes["quest_active"].properties.update(
        {
            "triggers": [
                {
                    "id": "trigger_01",
                    "name": "마을 도착",
                    "type": "location_enter",
                    "target": "town",
                }
            ],
            "triggers_met": [False],
            "choices": {"record": {"label": "기록으로 남깁니다"}},
        }
    )

    with pytest.raises(GraphQuestError, match="decision requires completed triggers"):
        plan_quest_decide(graph, "quest_active", "record")


def test_decide_rejects_unknown_choice():
    graph = _graph()
    graph.nodes["quest_active"].properties["choices"] = {
        "record": {"label": "기록으로 남깁니다"},
    }

    with pytest.raises(GraphQuestError, match="choice not found"):
        plan_quest_decide(graph, "quest_active", "missing")


def test_completed_quest_rewards_move_to_player():
    graph = _graph()
    graph.nodes["quest_completed"].properties["rewards"] = {
        "gold": 5,
        "exp": 10,
        "items": ["reward_sword"],
    }
    graph.edges["reward_of:reward_sword:quest_completed"] = GraphEdge(
        id="reward_of:reward_sword:quest_completed",
        type="reward_of",
        from_node_id="reward_sword",
        to_node_id="quest_completed",
    )

    result = plan_quest_rewards(graph, "quest_completed", "player_01")
    changed = _apply_all(graph, result.changes)

    player = changed.nodes["player_01"].properties
    assert player["gold"] == 6
    assert player["xp_pool"] == 12
    assert "reward_of:reward_sword:quest_completed" not in changed.edges
    assert "carries:player_01:reward_sword" in changed.edges


def test_completed_quest_rewards_remove_existing_item_location():
    graph = _graph()
    graph.nodes["quest_completed"].properties["rewards"] = {
        "gold": 0,
        "exp": 0,
        "items": ["reward_sword"],
    }
    graph.edges["located_at:reward_sword:town"] = GraphEdge(
        id="located_at:reward_sword:town",
        type="located_at",
        from_node_id="reward_sword",
        to_node_id="town",
    )

    result = plan_quest_rewards(graph, "quest_completed", "player_01")
    changed = _apply_all(graph, result.changes)

    assert "located_at:reward_sword:town" not in changed.edges
    assert "carries:player_01:reward_sword" in changed.edges


def test_completed_quest_rewards_use_selected_choice_rewards():
    graph = _graph()
    graph.nodes["quest_completed"].properties.update(
        {
            "selected_choice": "record",
            "choices": {
                "record": {
                    "label": "기록으로 남깁니다",
                    "rewards": {"gold": 2, "exp": 3, "items": ["reward_sword"]},
                },
                "release": {
                    "label": "흘려보냅니다",
                    "rewards": {"gold": 0, "exp": 0, "items": []},
                },
            },
            "rewards": {"gold": 99, "exp": 99, "items": []},
        }
    )

    result = plan_quest_rewards(graph, "quest_completed", "player_01")
    changed = _apply_all(graph, result.changes)

    player = changed.nodes["player_01"].properties
    assert player["gold"] == 3
    assert player["xp_pool"] == 5
    assert "carries:player_01:reward_sword" in changed.edges


def test_terminal_quests_reject_later_state_changes():
    with pytest.raises(GraphQuestError, match="terminal"):
        plan_quest_accept(_graph(), "quest_completed")
    with pytest.raises(GraphQuestError, match="terminal"):
        plan_quest_fail(_graph(), "quest_completed")


def test_missing_and_non_quest_nodes_are_rejected():
    with pytest.raises(GraphQuestError, match="missing quest"):
        plan_quest_accept(_graph(), "ghost")
    with pytest.raises(GraphQuestError, match="not a quest"):
        plan_quest_accept(_graph(), "town")


def test_quest_changes_are_individually_valid_graph_changes():
    graph = _graph()
    result = plan_quest_complete(graph, "quest_active", reason="done")

    for change in result.changes:
        graph = apply_graph_change(graph, change)

    assert graph.nodes["quest_active"].properties["status"] == "completed"
