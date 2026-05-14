from src.game.domain.graph import Graph, GraphEdge, GraphNode, apply_graph_changes
from src.game.engines.graph_social_quest import plan_social_quest_speak


def _character(character_id: str) -> GraphNode:
    return GraphNode(
        id=character_id,
        type="character",
        properties={"hp": 5, "max_hp": 5, "alive": True},
    )


def _quest(status: str = "pending", **properties) -> GraphNode:
    return GraphNode(
        id="q_missing_supplies",
        type="quest",
        properties={
            "status": status,
            "triggers": [],
            "triggers_met": [],
            "rewards": {"gold": 1, "exp": 0},
            **properties,
        },
    )


def _graph(*, quest_status: str = "pending", quest_props=None, edges=None) -> Graph:
    base_edges = {
        "relation:quartermaster_npc:player_01": GraphEdge(
            id="relation:quartermaster_npc:player_01",
            type="relation",
            from_node_id="quartermaster_npc",
            to_node_id="player_01",
            properties={"affinity": 20},
        ),
        "relation:village_resident:player_01": GraphEdge(
            id="relation:village_resident:player_01",
            type="relation",
            from_node_id="village_resident",
            to_node_id="player_01",
            properties={"affinity": 0},
        ),
        "relation:guide_npc:player_01": GraphEdge(
            id="relation:guide_npc:player_01",
            type="relation",
            from_node_id="guide_npc",
            to_node_id="player_01",
            properties={"affinity": 0},
        ),
    }
    if edges:
        base_edges.update(edges)
    return Graph(
        nodes={
            "player_01": _character("player_01"),
            "quartermaster_npc": _character("quartermaster_npc"),
            "village_resident": _character("village_resident"),
            "guide_npc": _character("guide_npc"),
            "q_missing_supplies": _quest(quest_status, **(quest_props or {})),
        },
        edges=base_edges,
    )


def _apply(graph: Graph, target_id: str | None, how: str, text: str) -> Graph:
    result = plan_social_quest_speak(
        graph,
        player_id="player_01",
        target_id=target_id,
        how=how,
        player_input=text,
    )
    assert result is not None
    return apply_graph_changes(graph, result.changes)


def test_report_route_completes_quest_and_changes_affinity():
    graph = _apply(
        _graph(),
        "village_resident",
        "hostile",
        "보급 담당자에게 주민을 고발합니다",
    )

    assert graph.nodes["q_missing_supplies"].properties["status"] == "completed"
    assert graph.nodes["q_missing_supplies"].properties["resolution_route"] == "report"
    assert (
        graph.edges["relation:quartermaster_npc:player_01"].properties["affinity"] == 25
    )
    assert (
        graph.edges["relation:village_resident:player_01"].properties["affinity"] == -5
    )
    assert graph.edges["relation:guide_npc:player_01"].properties["affinity"] == 0


def test_theft_accusation_wording_reports_resident():
    graph = _apply(
        _graph(),
        "village_resident",
        "hostile",
        "주민이 보급품을 훔쳤다고 말합니다",
    )

    assert graph.nodes["q_missing_supplies"].properties["resolution_route"] == "report"
    assert (
        graph.edges["relation:quartermaster_npc:player_01"].properties["affinity"] == 25
    )


def test_mediation_first_records_resident_reason_without_completing():
    graph = _apply(
        _graph(),
        "village_resident",
        "friendly",
        "누락된 보급품을 가져간 이유를 묻습니다",
    )

    quest = graph.nodes["q_missing_supplies"].properties
    assert quest["status"] == "pending"
    assert quest["resident_reason_known"] is True
    assert "resolution_route" not in quest
    assert (
        graph.edges["relation:village_resident:player_01"].properties["affinity"] == 2
    )


def test_missing_supplies_question_records_resident_reason():
    graph = _apply(
        _graph(),
        "village_resident",
        "friendly",
        "마을 주민에게 누락된 보급품을 묻습니다",
    )

    quest = graph.nodes["q_missing_supplies"].properties
    assert quest["resident_reason_known"] is True
    assert (
        graph.edges["relation:village_resident:player_01"].properties["affinity"] == 2
    )


def test_generic_resident_speech_does_not_mutate_quest():
    for how in ("friendly", "hostile"):
        result = plan_social_quest_speak(
            _graph(),
            player_id="player_01",
            target_id="village_resident",
            how=how,
            player_input="오늘 날씨 이야기를 나눕니다",
        )

        assert result is None


def test_generic_quartermaster_speech_does_not_block_or_resolve():
    result = plan_social_quest_speak(
        _graph(),
        player_id="player_01",
        target_id="quartermaster_npc",
        how="friendly",
        player_input="보급 담당자에게 안부를 묻습니다",
    )

    assert result is None


def test_active_and_locked_quests_can_be_planned():
    for status in ("active", "locked"):
        result = plan_social_quest_speak(
            _graph(quest_status=status),
            player_id="player_01",
            target_id="village_resident",
            how="friendly",
            player_input="누락된 보급품을 가져간 이유를 묻습니다",
        )

        assert result is not None
        assert result.kind == "reason_known"


def test_mediation_route_requires_reason_flag():
    result = plan_social_quest_speak(
        _graph(),
        player_id="player_01",
        target_id="quartermaster_npc",
        how="friendly",
        player_input="주민의 사정을 봐 달라고 설득합니다",
    )

    assert result is not None
    assert result.kind == "blocked"
    assert result.changes == []
    assert result.message_key == "runtime.social.missing_supplies.need_reason"


def test_mediation_route_completes_after_reason_flag():
    graph = _apply(
        _graph(quest_props={"resident_reason_known": True}),
        "quartermaster_npc",
        "friendly",
        "주민의 사정을 봐 달라고 설득합니다",
    )

    assert graph.nodes["q_missing_supplies"].properties["status"] == "completed"
    assert graph.nodes["q_missing_supplies"].properties["resolution_route"] == "mediate"
    assert (
        graph.edges["relation:quartermaster_npc:player_01"].properties["affinity"] == 23
    )
    assert (
        graph.edges["relation:village_resident:player_01"].properties["affinity"] == 8
    )
    assert graph.edges["relation:guide_npc:player_01"].properties["affinity"] == 5


def test_quiet_return_route_records_help_flag():
    graph = _apply(
        _graph(),
        "quartermaster_npc",
        "deceptive",
        "보급품을 조용히 돌려놓습니다",
    )

    assert graph.nodes["q_missing_supplies"].properties["status"] == "completed"
    assert (
        graph.nodes["q_missing_supplies"].properties["resolution_route"]
        == "quiet_return"
    )
    assert (
        graph.edges["relation:quartermaster_npc:player_01"].properties["affinity"] == 20
    )
    resident_relation = graph.edges["relation:village_resident:player_01"].properties
    assert resident_relation["affinity"] == 6
    assert resident_relation["flags"] == ["helped_quietly"]


def test_quiet_return_route_uses_wording_without_target():
    graph = _apply(
        _graph(),
        None,
        "deceptive",
        "보급품을 조용히 돌려놓습니다",
    )

    assert (
        graph.nodes["q_missing_supplies"].properties["resolution_route"]
        == "quiet_return"
    )
    assert (
        graph.edges["relation:village_resident:player_01"].properties["affinity"] == 6
    )


def test_quiet_return_creates_one_resident_relation_when_missing():
    graph = _graph()
    del graph.edges["relation:village_resident:player_01"]

    graph = _apply(
        graph,
        None,
        "deceptive",
        "quietly return the supplies",
    )

    relation_edges = [
        edge
        for edge in graph.edges.values()
        if edge.type == "relation"
        and {edge.from_node_id, edge.to_node_id} == {"village_resident", "player_01"}
    ]
    assert len(relation_edges) == 1
    assert relation_edges[0].properties["affinity"] == 6
    assert relation_edges[0].properties["flags"] == ["helped_quietly"]


def test_reverse_resident_relation_is_updated_instead_of_duplicated():
    graph = _graph()
    del graph.edges["relation:village_resident:player_01"]
    graph.edges["relation:player_01:village_resident"] = GraphEdge(
        id="relation:player_01:village_resident",
        type="relation",
        from_node_id="player_01",
        to_node_id="village_resident",
        properties={"affinity": 4, "flags": ["known"]},
    )

    graph = _apply(
        graph,
        None,
        "deceptive",
        "quietly return the supplies",
    )

    assert "relation:village_resident:player_01" not in graph.edges
    relation = graph.edges["relation:player_01:village_resident"].properties
    assert relation["affinity"] == 10
    assert relation["flags"] == ["known", "helped_quietly"]


def test_completed_quest_does_not_apply_again():
    result = plan_social_quest_speak(
        _graph(quest_status="completed", quest_props={"resolution_route": "report"}),
        player_id="player_01",
        target_id="village_resident",
        how="hostile",
        player_input="다시 고발합니다",
    )

    assert result is None
