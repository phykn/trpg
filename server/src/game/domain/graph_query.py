from src.game.domain.graph import (
    EdgeType,
    Graph,
    GraphEdge,
    GraphInvariantError,
    GraphNode,
    NodeType,
)


class GraphIndex:
    def __init__(self, graph: Graph) -> None:
        self.graph = graph
        self._from: dict[str, list[GraphEdge]] = {}
        self._to: dict[str, list[GraphEdge]] = {}
        for edge in graph.edges.values():
            self._from.setdefault(edge.from_node_id, []).append(edge)
            self._to.setdefault(edge.to_node_id, []).append(edge)

    @property
    def nodes(self) -> dict[str, GraphNode]:
        return self.graph.nodes

    @property
    def edges(self) -> dict[str, GraphEdge]:
        return self.graph.edges

    def edges_from(
        self,
        node_id: str,
        edge_type: EdgeType | None = None,
    ) -> list[GraphEdge]:
        return [
            edge
            for edge in self._from.get(node_id, [])
            if edge_type is None or edge.type == edge_type
        ]

    def edges_to(
        self,
        node_id: str,
        edge_type: EdgeType | None = None,
    ) -> list[GraphEdge]:
        return [
            edge
            for edge in self._to.get(node_id, [])
            if edge_type is None or edge.type == edge_type
        ]


GraphLike = Graph | GraphIndex


def require_node(graph: GraphLike, node_id: str) -> GraphNode:
    node = graph.nodes.get(node_id)
    if node is None:
        raise GraphInvariantError(f"missing node: {node_id}")
    return node


def nodes_of_type(graph: GraphLike, node_type: NodeType) -> list[GraphNode]:
    return [node for node in graph.nodes.values() if node.type == node_type]


def edges_from(
    graph: GraphLike,
    node_id: str,
    edge_type: EdgeType | None = None,
) -> list[GraphEdge]:
    if isinstance(graph, GraphIndex):
        return graph.edges_from(node_id, edge_type)
    return [
        edge
        for edge in graph.edges.values()
        if edge.from_node_id == node_id
        and (edge_type is None or edge.type == edge_type)
    ]


def edges_to(
    graph: GraphLike,
    node_id: str,
    edge_type: EdgeType | None = None,
) -> list[GraphEdge]:
    if isinstance(graph, GraphIndex):
        return graph.edges_to(node_id, edge_type)
    return [
        edge
        for edge in graph.edges.values()
        if edge.to_node_id == node_id and (edge_type is None or edge.type == edge_type)
    ]


def target_nodes(
    graph: GraphLike,
    node_id: str,
    edge_type: EdgeType,
) -> list[GraphNode]:
    return [
        require_node(graph, edge.to_node_id)
        for edge in edges_from(graph, node_id, edge_type)
    ]


def source_nodes(
    graph: GraphLike,
    node_id: str,
    edge_type: EdgeType,
) -> list[GraphNode]:
    return [
        require_node(graph, edge.from_node_id)
        for edge in edges_to(graph, node_id, edge_type)
    ]


def location_of(graph: GraphLike, node_id: str) -> str | None:
    for edge in edges_from(graph, node_id, "located_at"):
        return edge.to_node_id
    return None


def characters_at(
    graph: GraphLike,
    location_id: str,
    *,
    include_hidden: bool = False,
) -> list[str]:
    visible = [
        edge.from_node_id
        for edge in edges_to(graph, location_id, "located_at")
        if graph.nodes[edge.from_node_id].type == "character"
    ]
    if not include_hidden:
        return visible
    hidden = [
        edge.from_node_id
        for edge in edges_to(graph, location_id, "hidden_at")
        if graph.nodes[edge.from_node_id].type == "character"
    ]
    return [*visible, *hidden]


def items_at(
    graph: GraphLike,
    location_id: str,
    *,
    include_hidden: bool = False,
) -> list[str]:
    visible = [
        edge.from_node_id
        for edge in edges_to(graph, location_id, "located_at")
        if graph.nodes[edge.from_node_id].type == "item"
    ]
    if not include_hidden:
        return visible
    hidden = [
        edge.from_node_id
        for edge in edges_to(graph, location_id, "hidden_at")
        if graph.nodes[edge.from_node_id].type == "item"
    ]
    return [*visible, *hidden]


def inventory_of(graph: GraphLike, character_id: str) -> list[str]:
    return [edge.to_node_id for edge in edges_from(graph, character_id, "carries")]


def equipment_of(graph: GraphLike, character_id: str) -> list[GraphEdge]:
    return edges_from(graph, character_id, "equips")


def known_skills_of(graph: GraphLike, character_id: str) -> list[GraphEdge]:
    return edges_from(graph, character_id, "knows_skill")


def race_of(graph: GraphLike, character_id: str) -> str | None:
    for edge in edges_from(graph, character_id, "belongs_to_race"):
        return edge.to_node_id
    return None


def quest_targets_of(graph: GraphLike, quest_id: str) -> list[str]:
    return [edge.from_node_id for edge in edges_to(graph, quest_id, "target_of")]


def quest_requirements_of(graph: GraphLike, quest_id: str) -> list[str]:
    return [edge.from_node_id for edge in edges_to(graph, quest_id, "required_by")]


def quest_reward_items_of(graph: GraphLike, quest_id: str) -> list[str]:
    return [edge.from_node_id for edge in edges_to(graph, quest_id, "reward_of")]


def quests_in_chapter(graph: GraphLike, chapter_id: str) -> list[str]:
    return [
        edge.from_node_id for edge in edges_to(graph, chapter_id, "part_of_chapter")
    ]
