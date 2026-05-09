import pytest

from src.game.domain.graph import Graph, GraphNode, apply_graph_change
from src.game.engines.graph_quest import (
    GraphQuestError,
    plan_quest_abandon,
    plan_quest_accept,
    plan_quest_complete,
    plan_quest_fail,
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
