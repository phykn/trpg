"""Read-only graph questions; everything that follows edges goes through here."""

from src.content.schema import PLAYER

from .graph import Edge, Graph


def place_of(graph: Graph, node_id: str) -> str | None:
    edges = graph.out(node_id, "at")
    return edges[0].dst if edges else None


def holder(graph: Graph, item: str) -> str | None:
    edges = graph.into(item, "carries")
    return edges[0].src if edges else None


def carried(graph: Graph, who: str = PLAYER) -> list[str]:
    return [e.dst for e in graph.out(who, "carries")]


def present(graph: Graph, place: str) -> list[str]:
    return [
        e.src
        for e in graph.into(place, "at")
        if e.src != PLAYER and graph.nodes[e.src].type == "character"
    ]


def items_at(graph: Graph, place: str) -> list[str]:
    return [e.src for e in graph.into(place, "at") if graph.nodes[e.src].type == "item"]


def knows(graph: Graph, who: str, knowledge: str) -> bool:
    return graph.edge("knows", who, knowledge) is not None


def known(graph: Graph, who: str = PLAYER) -> list[str]:
    return [e.dst for e in graph.out(who, "knows")]


def exits(graph: Graph, place: str) -> list[tuple[str, bool]]:
    return [(e.dst, bool(e.props.get("open", True))) for e in graph.out(place, "connects")]


def relation_edge(graph: Graph, character: str) -> Edge | None:
    return graph.edge("relation", character, PLAYER)


def relation(graph: Graph, character: str) -> int:
    edge = relation_edge(graph, character)
    return int(edge.props.get("value", 0)) if edge else 0


def memories(graph: Graph, character: str) -> list[dict]:
    edge = relation_edge(graph, character)
    return list(edge.props.get("memories", [])) if edge else []


def companions(graph: Graph) -> list[str]:
    return [e.dst for e in graph.out(PLAYER, "companion")]


def claims(graph: Graph, character: str) -> list[Edge]:
    return [e for e in graph.out(PLAYER, "claimed") if e.dst == character]
