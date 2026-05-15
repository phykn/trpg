from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
        from .validation import validate_graph

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
