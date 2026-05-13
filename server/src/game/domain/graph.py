from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator


NodeType = Literal[
    "character",
    "item",
    "location",
    "quest",
    "skill",
    "race",
    "chapter",
]

EdgeType = Literal[
    "located_at",
    "hidden_at",
    "carries",
    "equips",
    "connects_to",
    "has_companion",
    "knows_skill",
    "belongs_to_race",
    "grants_skill",
    "gives_quest",
    "target_of",
    "required_by",
    "reward_of",
    "part_of_chapter",
    "relation",
]


class GraphInvariantError(ValueError):
    pass


class GraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: NodeType
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    type: EdgeType
    from_node_id: str = Field(alias="from")
    to_node_id: str = Field(alias="to")
    properties: dict[str, Any] = Field(default_factory=dict)


class Graph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: dict[str, GraphNode] = Field(default_factory=dict)
    edges: dict[str, GraphEdge] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _keys_match_ids(self) -> "Graph":
        for key, node in self.nodes.items():
            if key != node.id:
                raise ValueError(f"node key {key!r} does not match node id {node.id!r}")
        for key, edge in self.edges.items():
            if key != edge.id:
                raise ValueError(f"edge key {key!r} does not match edge id {edge.id!r}")
        return self

    @model_validator(mode="after")
    def _loaded_graph_is_valid(self) -> "Graph":
        validate_graph(self)
        return self


class AddNodeChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["add_node"]
    node: GraphNode


class SetNodePropertyChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["set_node_property"]
    node_id: str
    path: str
    value: Any


class AddEdgeChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["add_edge"]
    edge: GraphEdge


class SetEdgePropertyChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["set_edge_property"]
    edge_id: str
    path: str
    value: Any


class RemoveEdgeChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["remove_edge"]
    edge_id: str


GraphChange = Annotated[
    AddNodeChange
    | SetNodePropertyChange
    | AddEdgeChange
    | SetEdgePropertyChange
    | RemoveEdgeChange,
    Field(discriminator="type"),
]

_GRAPH_CHANGE_ADAPTER = TypeAdapter(GraphChange)

_EDGE_NODE_TYPES: dict[EdgeType, tuple[set[NodeType], set[NodeType]]] = {
    "located_at": ({"character", "item"}, {"location"}),
    "hidden_at": ({"character", "item"}, {"location"}),
    "carries": ({"character"}, {"item"}),
    "equips": ({"character"}, {"item"}),
    "connects_to": ({"location"}, {"location"}),
    "has_companion": ({"character"}, {"character"}),
    "knows_skill": ({"character"}, {"skill"}),
    "belongs_to_race": ({"character"}, {"race"}),
    "grants_skill": ({"race"}, {"skill"}),
    "gives_quest": ({"character", "location"}, {"quest"}),
    "target_of": ({"character", "item", "location"}, {"quest"}),
    "required_by": ({"character", "item", "location"}, {"quest"}),
    "reward_of": ({"item"}, {"quest"}),
    "part_of_chapter": ({"quest"}, {"chapter"}),
    "relation": ({"character"}, {"character"}),
}

_ITEM_PLACEMENT_FROM_ITEM: frozenset[EdgeType] = frozenset(
    {"located_at", "hidden_at", "reward_of"}
)
_ITEM_PLACEMENT_TO_ITEM: frozenset[EdgeType] = frozenset({"carries", "equips"})


def parse_graph_change(data: Any) -> GraphChange:
    return _GRAPH_CHANGE_ADAPTER.validate_python(data)


def apply_graph_change(graph: Graph, change: GraphChange) -> Graph:
    return apply_graph_changes(graph, [change])


def apply_graph_changes(graph: Graph, changes: list[GraphChange]) -> Graph:
    next_graph = graph.model_copy(deep=True)

    for change in changes:
        _apply_graph_change_in_place(next_graph, change)
    validate_graph(next_graph)
    return next_graph


def _apply_graph_change_in_place(graph: Graph, change: GraphChange) -> None:
    if isinstance(change, AddNodeChange):
        if change.node.id in graph.nodes:
            raise GraphInvariantError(f"duplicate node: {change.node.id}")
        graph.nodes[change.node.id] = change.node
    elif isinstance(change, SetNodePropertyChange):
        node = graph.nodes.get(change.node_id)
        if node is None:
            raise GraphInvariantError(f"missing node: {change.node_id}")
        _set_property(node.properties, change.path, change.value)
    elif isinstance(change, AddEdgeChange):
        if change.edge.id in graph.edges:
            raise GraphInvariantError(f"duplicate edge: {change.edge.id}")
        graph.edges[change.edge.id] = change.edge
    elif isinstance(change, SetEdgePropertyChange):
        edge = graph.edges.get(change.edge_id)
        if edge is None:
            raise GraphInvariantError(f"missing edge: {change.edge_id}")
        _set_property(edge.properties, change.path, change.value)
    elif isinstance(change, RemoveEdgeChange):
        if change.edge_id not in graph.edges:
            raise GraphInvariantError(f"missing edge: {change.edge_id}")
        del graph.edges[change.edge_id]


def validate_graph(graph: Graph) -> None:
    _validate_edge_endpoints(graph)
    _validate_edge_node_types(graph)
    _validate_item_placement(graph)
    _validate_character_location(graph)
    _validate_quest_trigger_targets(graph)


def _set_property(properties: dict[str, Any], path: str, value: Any) -> None:
    parts = [part for part in path.split(".") if part]
    if not parts:
        raise GraphInvariantError("empty property path")

    current = properties
    for part in parts[:-1]:
        nested = current.get(part)
        if not isinstance(nested, dict):
            nested = {}
            current[part] = nested
        current = nested
    current[parts[-1]] = value


def _validate_edge_endpoints(graph: Graph) -> None:
    for edge in graph.edges.values():
        if edge.from_node_id not in graph.nodes:
            raise GraphInvariantError(f"missing node: {edge.from_node_id}")
        if edge.to_node_id not in graph.nodes:
            raise GraphInvariantError(f"missing node: {edge.to_node_id}")


def _validate_edge_node_types(graph: Graph) -> None:
    for edge in graph.edges.values():
        from_type = graph.nodes[edge.from_node_id].type
        to_type = graph.nodes[edge.to_node_id].type
        allowed_from, allowed_to = _EDGE_NODE_TYPES[edge.type]
        if from_type not in allowed_from or to_type not in allowed_to:
            raise GraphInvariantError(
                "edge type mismatch: "
                f"{edge.type} cannot connect {from_type} to {to_type}"
            )


def _validate_item_placement(graph: Graph) -> None:
    placements: dict[str, list[str]] = {}
    for edge in graph.edges.values():
        if edge.type in _ITEM_PLACEMENT_FROM_ITEM:
            item_id = edge.from_node_id
        elif edge.type in _ITEM_PLACEMENT_TO_ITEM:
            item_id = edge.to_node_id
        else:
            continue
        if graph.nodes[item_id].type != "item":
            continue
        placements.setdefault(item_id, []).append(edge.id)

    for item_id, edge_ids in placements.items():
        if len(edge_ids) > 1:
            joined = ", ".join(edge_ids)
            raise GraphInvariantError(f"item placement conflict: {item_id} ({joined})")


def _validate_character_location(graph: Graph) -> None:
    locations: dict[str, list[str]] = {}
    for edge in graph.edges.values():
        if edge.type != "located_at":
            continue
        if graph.nodes[edge.from_node_id].type != "character":
            continue
        locations.setdefault(edge.from_node_id, []).append(edge.id)

    for character_id, edge_ids in locations.items():
        if len(edge_ids) > 1:
            joined = ", ".join(edge_ids)
            raise GraphInvariantError(
                f"character location conflict: {character_id} ({joined})"
            )


def _validate_quest_trigger_targets(graph: Graph) -> None:
    for quest in graph.nodes.values():
        if quest.type != "quest":
            continue
        for trigger in _dicts(quest.properties.get("triggers")):
            target_id = trigger.get("target_id")
            if isinstance(target_id, str) and target_id not in graph.nodes:
                raise GraphInvariantError(
                    f"quest trigger target missing: {quest.id} -> {target_id}"
                )


def _dicts(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)]
