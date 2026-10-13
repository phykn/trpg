import pytest
from src.game.graph import Graph, GraphInvariantError, GraphNode
from src.game.graph.apply import apply_graph_changes, parse_graph_change


@pytest.mark.parametrize("target, target_id", [("node", "place"), ("edge", "location")])
@pytest.mark.parametrize("replace_details", [False, True])
@pytest.mark.parametrize("invalid", [False, True])
def test_graph_changes_do_not_share_mutable_inputs(
    target, target_id, replace_details, invalid
):
    graph = Graph(nodes={"player": GraphNode(id="player", type="character")})
    node = {
        "id": "place",
        "type": "location",
        "properties": {"details": {"seen": False}},
    }
    edge = {
        "id": "location",
        "type": "located_at",
        "from": "player",
        "to": "place",
        "properties": {"details": {"seen": False}},
    }
    changes = [
        parse_graph_change({"type": "add_node", "node": node}),
        parse_graph_change({"type": "add_edge", "edge": edge}),
    ]
    if replace_details:
        changes.append(
            parse_graph_change(
                {
                    "type": f"set_{target}_property",
                    f"{target}_id": target_id,
                    "path": "details",
                    "value": {"seen": False},
                }
            )
        )
    changes.append(
        parse_graph_change(
            {
                "type": f"set_{target}_property",
                f"{target}_id": target_id,
                "path": "details.seen",
                "value": True,
            }
        )
    )
    if invalid:
        changes.append(
            parse_graph_change({"type": "remove_edge", "edge_id": "missing"})
        )
    before = [change.model_dump(mode="json") for change in changes]
    original = graph.model_dump(mode="json")

    if invalid:
        with pytest.raises(GraphInvariantError, match="missing edge"):
            apply_graph_changes(graph, changes)
    else:
        changed = apply_graph_changes(graph, changes)
        props = (
            changed.nodes["place"].properties
            if target == "node"
            else changed.edges["location"].properties
        )
        assert props["details"]["seen"] is True
        props["details"]["later"] = True

    assert graph.model_dump(mode="json") == original
    assert [change.model_dump(mode="json") for change in changes] == before
