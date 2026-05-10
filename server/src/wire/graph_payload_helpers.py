from typing import Literal

from src.game.domain.content import RuntimeContent, node_label, node_value
from src.game.domain.graph import GraphNode
from src.llm.context.graph_combat import hp_state, mp_state
from src.wire.models import GraphResourcePayload


def resource(
    node: GraphNode,
    current_key: Literal["hp", "mp"],
    max_key: Literal["max_hp", "max_mp"],
) -> GraphResourcePayload:
    current = int_prop(node, current_key)
    maximum = int_prop(node, max_key)
    state = (
        hp_state(current, maximum)
        if current_key == "hp"
        else mp_state(current, maximum)
    )
    return GraphResourcePayload(
        current=current,
        maximum=maximum,
        state=state or "drained",
    )


def optional_resource(
    node: GraphNode,
    current_key: Literal["hp", "mp"],
    max_key: Literal["max_hp", "max_mp"],
) -> GraphResourcePayload | None:
    current = node.properties.get(current_key)
    maximum = node.properties.get(max_key)
    if not isinstance(current, int) or not isinstance(maximum, int) or maximum <= 0:
        return None
    return resource(node, current_key, max_key)


def require_node(graph, node_id: str, node_type: str) -> GraphNode:
    node = graph.nodes.get(node_id)
    if node is None:
        raise ValueError(f"missing node: {node_id}")
    if node.type != node_type:
        raise ValueError(f"node {node_id} is not {node_type}")
    return node


def int_prop(node: GraphNode, key: str) -> int:
    value = node.properties.get(key)
    if not isinstance(value, int):
        raise ValueError(f"missing numeric property {node.id}.{key}")
    return value


def int_prop_default(node: GraphNode, key: str, default: int) -> int:
    value = node.properties.get(key)
    return value if isinstance(value, int) else default


def node_name(node: GraphNode, content: RuntimeContent | None = None) -> str:
    if content is not None:
        return node_label(content, node)
    return optional_str(node.properties.get("name")) or node.id


def static_value(
    node: GraphNode,
    key: str,
    content: RuntimeContent | None = None,
) -> object:
    if content is not None:
        return node_value(content, node, key)
    return node.properties.get(key)


def optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
