"""World graph: typed nodes, typed edges, and the only code that adds or removes edges."""

from typing import Any, Literal

from pydantic import Field

from src.content.schema import Model

NodeType = Literal["place", "character", "item", "knowledge", "quest", "skill"]
EdgeType = Literal["at", "connects", "carries", "knows", "relation", "companion", "claimed"]


class GraphError(ValueError):
    pass


class Node(Model):
    id: str
    type: NodeType
    props: dict[str, Any] = Field(default_factory=dict)


class Edge(Model):
    id: str
    type: EdgeType
    src: str
    dst: str
    props: dict[str, Any] = Field(default_factory=dict)


class Graph(Model):
    nodes: dict[str, Node] = Field(default_factory=dict)
    edges: dict[str, Edge] = Field(default_factory=dict)

    def add_node(self, node_id: str, node_type: NodeType, **props: Any) -> Node:
        if node_id in self.nodes:
            raise GraphError(f"duplicate node: {node_id}")
        node = Node(id=node_id, type=node_type, props=props)
        self.nodes[node_id] = node
        return node

    def link(self, edge_type: EdgeType, src: str, dst: str, key: str = "", **props: Any) -> Edge:
        for end in (src, dst):
            if end not in self.nodes:
                raise GraphError(f"missing node: {end}")
        edge_id = ":".join(part for part in (edge_type, src, dst, key) if part)
        if edge_id in self.edges:
            raise GraphError(f"duplicate edge: {edge_id}")
        edge = Edge(id=edge_id, type=edge_type, src=src, dst=dst, props=props)
        self.edges[edge_id] = edge
        return edge

    def unlink(self, edge_id: str) -> None:
        if edge_id not in self.edges:
            raise GraphError(f"missing edge: {edge_id}")
        del self.edges[edge_id]

    def out(self, src: str, edge_type: EdgeType | None = None) -> list[Edge]:
        return [
            e for e in self.edges.values() if e.src == src and edge_type in (None, e.type)
        ]

    def into(self, dst: str, edge_type: EdgeType | None = None) -> list[Edge]:
        return [
            e for e in self.edges.values() if e.dst == dst and edge_type in (None, e.type)
        ]

    def edge(self, edge_type: EdgeType, src: str, dst: str) -> Edge | None:
        return self.edges.get(f"{edge_type}:{src}:{dst}")

    def of_type(self, node_type: NodeType) -> list[Node]:
        return [n for n in self.nodes.values() if n.type == node_type]

    def validate(self) -> None:
        for edge in self.edges.values():
            if edge.src not in self.nodes or edge.dst not in self.nodes:
                raise GraphError(f"dangling edge: {edge.id}")
        for node in self.nodes.values():
            if node.type in ("character", "item"):
                holders = [e for e in self.into(node.id, "carries")] + self.out(node.id, "at")
                if len(holders) > 1:
                    raise GraphError(f"{node.id} is in more than one place")
