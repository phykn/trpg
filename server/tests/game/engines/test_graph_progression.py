from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.graph.apply import apply_graph_change
from src.game.engines.graph.progression import (
    plan_progression_after_quest_completion,
)


def _graph() -> Graph:
    return Graph(
        nodes={
            "chapter_01": GraphNode(
                id="chapter_01",
                type="chapter",
                properties={"status": "active", "quests": ["q1"]},
            ),
            "chapter_02": GraphNode(
                id="chapter_02",
                type="chapter",
                properties={
                    "status": "locked",
                    "quests": ["q2", "q3"],
                    "prerequisites": ["chapter_01"],
                },
            ),
            "q1": GraphNode(
                id="q1",
                type="quest",
                properties={
                    "status": "completed",
                    "required": True,
                    "prerequisites": [],
                },
            ),
            "q2": GraphNode(
                id="q2",
                type="quest",
                properties={
                    "status": "locked",
                    "required": True,
                    "prerequisites": ["q1"],
                },
            ),
            "q3": GraphNode(
                id="q3",
                type="quest",
                properties={
                    "status": "locked",
                    "required": True,
                    "prerequisites": ["q2"],
                },
            ),
            "forest": GraphNode(
                id="forest",
                type="location",
                properties={"name": "숲"},
            ),
        },
        edges={
            "part_of_chapter:q1:chapter_01": GraphEdge(
                id="part_of_chapter:q1:chapter_01",
                type="part_of_chapter",
                from_node_id="q1",
                to_node_id="chapter_01",
            ),
            "part_of_chapter:q2:chapter_02": GraphEdge(
                id="part_of_chapter:q2:chapter_02",
                type="part_of_chapter",
                from_node_id="q2",
                to_node_id="chapter_02",
            ),
            "part_of_chapter:q3:chapter_02": GraphEdge(
                id="part_of_chapter:q3:chapter_02",
                type="part_of_chapter",
                from_node_id="q3",
                to_node_id="chapter_02",
            ),
        },
    )


def _apply_all(graph: Graph, changes) -> Graph:
    for change in changes:
        graph = apply_graph_change(graph, change)
    return graph


def test_progression_unlocks_next_required_quest_as_pending_and_chapter():
    graph = _graph()

    result = plan_progression_after_quest_completion(
        graph,
        completed_quest_ids=["q1"],
        active_quest_id="q1",
    )
    changed = _apply_all(graph, result.changes)

    assert result.next_active_quest_id is None
    assert result.completed_chapter_ids == ["chapter_01"]
    assert changed.nodes["q2"].properties["status"] == "pending"
    assert changed.nodes["chapter_01"].properties["status"] == "completed"
    assert changed.nodes["chapter_02"].properties["status"] == "active"


def test_progression_auto_activates_marked_unlocked_quest_when_slot_opens():
    graph = _graph()
    graph.nodes["q2"].properties["auto_activate_when_unlocked"] = True

    result = plan_progression_after_quest_completion(
        graph,
        completed_quest_ids=["q1"],
        active_quest_id="q1",
    )
    changed = _apply_all(graph, result.changes)

    assert result.next_active_quest_id == "q2"
    assert changed.nodes["q2"].properties["status"] == "active"


def test_progression_marks_scenario_completed_when_no_required_quest_remains():
    graph = _graph()
    graph.nodes["chapter_01"].properties["status"] = "completed"
    graph.nodes["chapter_02"].properties["status"] = "active"
    graph.nodes["q2"].properties["status"] = "completed"
    graph.nodes["q3"].properties["status"] = "completed"

    result = plan_progression_after_quest_completion(
        graph,
        completed_quest_ids=["q3"],
        active_quest_id="q3",
    )
    changed = _apply_all(graph, result.changes)

    assert result.next_active_quest_id is None
    assert result.completed_chapter_ids == ["chapter_02"]
    assert result.scenario_completed is True
    assert changed.nodes["chapter_02"].properties["status"] == "completed"


def test_progression_ignores_legacy_generated_quest_for_scenario_completion():
    graph = _graph()
    graph.nodes["chapter_01"].properties["status"] = "completed"
    graph.nodes["chapter_02"].properties["status"] = "completed"
    graph.nodes["q2"].properties["status"] = "completed"
    graph.nodes["q3"].properties["status"] = "completed"
    graph.nodes["quest_generated"] = GraphNode(
        id="quest_generated",
        type="quest",
        properties={
            "title": "다음 단서 확인",
            "description": "방금 확인한 목표를 진행하기 위한 다음 단서를 찾습니다.",
            "status": "pending",
            "stability": "chapter",
            "turn_id": 2,
        },
    )

    result = plan_progression_after_quest_completion(
        graph,
        completed_quest_ids=["q3"],
        active_quest_id="q3",
    )

    assert result.scenario_completed is True


def test_progression_keeps_existing_active_quest_when_completed_quest_was_not_active():
    graph = _graph()
    graph.nodes["q2"].properties["status"] = "active"

    result = plan_progression_after_quest_completion(
        graph,
        completed_quest_ids=["q1"],
        active_quest_id="q2",
    )

    assert result.next_active_quest_id == "q2"


def test_progression_keeps_pending_required_quest_when_active_slot_opens():
    graph = _graph()
    graph.nodes["chapter_01"].properties["status"] = "completed"
    graph.nodes["chapter_02"].properties["status"] = "active"
    graph.nodes["q2"].properties["status"] = "pending"
    graph.nodes["q2"].properties["prerequisites"] = ["q1"]
    graph.nodes["q3"].properties["status"] = "completed"

    result = plan_progression_after_quest_completion(
        graph,
        completed_quest_ids=["q3"],
        active_quest_id="q3",
    )
    changed = _apply_all(graph, result.changes)

    assert result.next_active_quest_id is None
    assert changed.nodes["q2"].properties["status"] == "pending"


def test_progression_does_not_auto_complete_pending_location_quest_before_acceptance():
    graph = _graph()
    graph.nodes["chapter_01"].properties["status"] = "completed"
    graph.nodes["chapter_02"].properties["status"] = "active"
    graph.nodes["q2"].properties.update(
        {
            "status": "pending",
            "triggers": [{"type": "location_enter", "target": "forest"}],
            "auto_complete_when_satisfied": True,
        }
    )

    result = plan_progression_after_quest_completion(
        graph,
        completed_quest_ids=["q1"],
        active_quest_id="q1",
        satisfied_location_ids={"forest"},
    )
    changed = _apply_all(graph, result.changes)

    assert result.auto_completed_quest_ids == []
    assert changed.nodes["q2"].properties.get("triggers_met") is None
    assert changed.nodes["q2"].properties["status"] == "pending"


def test_progression_auto_completes_active_location_quest_already_satisfied():
    graph = _graph()
    graph.nodes["chapter_01"].properties["status"] = "completed"
    graph.nodes["chapter_02"].properties["status"] = "active"
    graph.nodes["q2"].properties.update(
        {
            "status": "active",
            "triggers": [{"type": "location_enter", "target": "forest"}],
            "auto_complete_when_satisfied": True,
        }
    )

    result = plan_progression_after_quest_completion(
        graph,
        completed_quest_ids=["q1"],
        active_quest_id="q2",
        satisfied_location_ids={"forest"},
    )
    changed = _apply_all(graph, result.changes)

    assert result.auto_completed_quest_ids == ["q2"]
    assert changed.nodes["q2"].properties["triggers_met"] == [True]
    assert changed.nodes["q2"].properties["status"] == "completed"


def test_progression_does_not_auto_complete_pending_location_quest_already_visited():
    graph = _graph()
    graph.nodes["q2"].properties["triggers"] = [
        {"type": "location_enter", "target": "forest"}
    ]

    result = plan_progression_after_quest_completion(
        graph,
        completed_quest_ids=["q1"],
        active_quest_id="q1",
        satisfied_location_ids={"forest"},
    )
    changed = _apply_all(graph, result.changes)

    assert result.auto_completed_quest_ids == []
    assert result.next_active_quest_id is None
    assert changed.nodes["q2"].properties["status"] == "pending"
    assert changed.nodes["q2"].properties.get("triggers_met") is None
    assert changed.nodes["q3"].properties["status"] == "locked"


def test_progression_keeps_choice_location_quest_pending_until_accepted():
    graph = _graph()
    graph.nodes["q2"].properties["triggers"] = [
        {"type": "location_enter", "target": "forest"}
    ]
    graph.nodes["q2"].properties["choices"] = {
        "record": {"label": "기록으로 남깁니다"},
        "release": {"label": "흘려보냅니다"},
    }

    result = plan_progression_after_quest_completion(
        graph,
        completed_quest_ids=["q1"],
        active_quest_id="q1",
        satisfied_location_ids={"forest"},
    )
    changed = _apply_all(graph, result.changes)

    assert result.auto_completed_quest_ids == []
    assert result.next_active_quest_id is None
    assert changed.nodes["q2"].properties["status"] == "pending"
    assert changed.nodes["q2"].properties.get("triggers_met") is None
