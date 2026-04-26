from collections import defaultdict
from typing import NamedTuple

from ..domain.state import GameState


class Edge(NamedTuple):
    type: str
    from_id: str
    to_id: str


class GameGraph:
    def __init__(self):
        self._node_types: dict[str, str] = {}
        self._out: dict[str, list[Edge]] = defaultdict(list)

    def add_node(self, node_id: str, entity_type: str) -> None:
        self._node_types[node_id] = entity_type

    def add_edge(self, from_id: str, to_id: str, edge_type: str) -> None:
        self._out[from_id].append(
            Edge(type=edge_type, from_id=from_id, to_id=to_id)
        )

    def get_edges(self, from_id: str, edge_type: str | None = None) -> list[Edge]:
        edges = self._out.get(from_id, [])
        if edge_type is not None:
            return [e for e in edges if e.type == edge_type]
        return list(edges)

    def get_node_type(self, node_id: str) -> str | None:
        return self._node_types.get(node_id)


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
        for _, item_id in char.equipment.equipped_items():
            g.add_edge(cid, item_id, "equips")
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
