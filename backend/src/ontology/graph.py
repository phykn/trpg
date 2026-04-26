from collections import defaultdict, deque
from typing import NamedTuple

from ..domain.entities import EQUIPMENT_SLOTS
from ..domain.state import GameState


class Edge(NamedTuple):
    type: str
    from_id: str
    to_id: str
    attrs: dict | None = None


class GameGraph:
    def __init__(self):
        self._node_types: dict[str, str] = {}
        self._out: dict[str, list[Edge]] = defaultdict(list)

    def add_node(self, node_id: str, entity_type: str) -> None:
        self._node_types[node_id] = entity_type

    def add_edge(
        self,
        from_id: str,
        to_id: str,
        edge_type: str,
        attrs: dict | None = None,
    ) -> None:
        self._out[from_id].append(
            Edge(type=edge_type, from_id=from_id, to_id=to_id, attrs=attrs)
        )

    def get_edges(self, from_id: str, edge_type: str | None = None) -> list[Edge]:
        edges = self._out.get(from_id, [])
        if edge_type is not None:
            return [e for e in edges if e.type == edge_type]
        return list(edges)

    def get_node_type(self, node_id: str) -> str | None:
        return self._node_types.get(node_id)

    def neighbors(
        self,
        node_id: str,
        depth: int = 1,
        edge_types: list[str] | None = None,
    ) -> dict[str, list[Edge]]:
        """BFS up to `depth` hops. Returns {neighbor_id: path_edges_from_root}."""
        parent_edge: dict[str, Edge] = {}
        parent_of: dict[str, str] = {}
        visited: set[str] = {node_id}
        queue: deque[tuple[str, int]] = deque([(node_id, 0)])

        while queue:
            current, d = queue.popleft()
            if d >= depth:
                continue
            for edge in self._out.get(current, []):
                if edge_types is not None and edge.type not in edge_types:
                    continue
                neighbor = edge.to_id
                if neighbor not in visited:
                    visited.add(neighbor)
                    parent_edge[neighbor] = edge
                    parent_of[neighbor] = current
                    queue.append((neighbor, d + 1))

        result: dict[str, list[Edge]] = {}
        for neighbor in parent_edge:
            path: list[Edge] = []
            cur = neighbor
            while cur in parent_edge:
                path.append(parent_edge[cur])
                cur = parent_of[cur]
            path.reverse()
            result[neighbor] = path
        return result


def build_graph(state: GameState) -> GameGraph:
    g = GameGraph()
    for cid in state.characters:
        g.add_node(cid, "character")
    for iid in state.items:
        g.add_node(iid, "item")
    for lid in state.locations:
        g.add_node(lid, "location")
    for qid in state.quests:
        g.add_node(qid, "quest")
    _build_character_edges(g, state)
    _build_location_edges(g, state)
    _build_quest_edges(g, state)
    return g


def _build_character_edges(g: GameGraph, state: GameState) -> None:
    for cid, char in state.characters.items():
        if char.location_id:
            g.add_edge(cid, char.location_id, "located_at")
        for slot in EQUIPMENT_SLOTS:
            item_id = getattr(char.equipment, slot)
            if item_id:
                g.add_edge(cid, item_id, "equips", attrs={"slot": slot})
        for item_id in char.inventory_ids:
            if item_id:
                g.add_edge(cid, item_id, "carries")


def _build_location_edges(g: GameGraph, state: GameState) -> None:
    for lid, loc in state.locations.items():
        for conn in loc.connections:
            if conn.target_id:
                g.add_edge(lid, conn.target_id, "connects_to")
                if conn.key_item_id:
                    g.add_edge(conn.key_item_id, conn.target_id, "unlocks")


def _build_quest_edges(g: GameGraph, state: GameState) -> None:
    for qid, quest in state.quests.items():
        if quest.giver_id:
            g.add_edge(quest.giver_id, qid, "gives_quest")
        for trig in quest.triggers:
            if trig.target_id:
                g.add_edge(trig.target_id, qid, "required_by")
                if trig.type == "character_death":
                    g.add_edge(trig.target_id, qid, "kill_target_of")
        for item_id in quest.rewards.items:
            if item_id:
                g.add_edge(item_id, qid, "reward_of")
