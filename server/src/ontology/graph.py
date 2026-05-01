from collections import defaultdict
from typing import Any, NamedTuple

from ..domain.state import GameState


class Edge(NamedTuple):
    type: str
    from_id: str
    to_id: str
    attrs: dict[str, Any] | None = None


class GameGraph:
    def __init__(self) -> None:
        self._node_types: dict[str, str] = {}
        self._out: dict[str, list[Edge]] = defaultdict(list)
        self._in: dict[str, list[Edge]] = defaultdict(list)

    def add_node(self, node_id: str, entity_type: str) -> None:
        self._node_types[node_id] = entity_type

    def add_edge(
        self,
        from_id: str,
        to_id: str,
        edge_type: str,
        attrs: dict[str, Any] | None = None,
    ) -> None:
        edge = Edge(type=edge_type, from_id=from_id, to_id=to_id, attrs=attrs)
        self._out[from_id].append(edge)
        self._in[to_id].append(edge)

    def get_edges(self, from_id: str, edge_type: str | None = None) -> list[Edge]:
        edges = self._out.get(from_id, [])
        if edge_type is not None:
            return [e for e in edges if e.type == edge_type]
        return list(edges)

    def get_in_edges(self, to_id: str, edge_type: str | None = None) -> list[Edge]:
        edges = self._in.get(to_id, [])
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
    for sid in state.skills:
        g.add_node(sid, "skill")
    for rid in state.races:
        g.add_node(rid, "race")
    for chid in state.chapters:
        g.add_node(chid, "chapter")
    _build_character_edges(g, state)
    _build_location_edges(g, state)
    _build_quest_edges(g, state)
    _build_chapter_edges(g, state)
    _build_race_edges(g, state)
    return g


def _build_character_edges(g: GameGraph, state: GameState) -> None:
    for cid, char in state.characters.items():
        if char.location_id:
            g.add_edge(cid, char.location_id, "located_at")
        if char.race_id:
            g.add_edge(cid, char.race_id, "belongs_to_race")
        for slot, item_id in char.equipment.equipped_items():
            g.add_edge(cid, item_id, "equips", attrs={"slot": slot})
        for item_id in char.inventory_ids:
            if item_id:
                g.add_edge(cid, item_id, "carries")
        for sid in char.racial_skill_ids:
            if sid:
                g.add_edge(cid, sid, "knows_skill", attrs={"source": "racial"})
        for sid in char.learned_skill_ids:
            if sid:
                g.add_edge(cid, sid, "knows_skill", attrs={"source": "learned"})
        for companion_id in char.companions:
            if companion_id:
                g.add_edge(cid, companion_id, "has_companion")


def _build_location_edges(g: GameGraph, state: GameState) -> None:
    for lid, loc in state.locations.items():
        for conn in loc.connections:
            if not conn.target_id:
                continue
            attrs: dict[str, Any] = {}
            if conn.difficulty:
                attrs["difficulty"] = conn.difficulty
            if conn.key_item_id:
                attrs["key_item_id"] = conn.key_item_id
            g.add_edge(
                lid, conn.target_id, "connects_to", attrs=attrs or None
            )
            if conn.key_item_id:
                g.add_edge(conn.key_item_id, conn.target_id, "unlocks")
        for item_id in loc.item_ids:
            if item_id:
                g.add_edge(item_id, lid, "located_in")


def _build_quest_edges(g: GameGraph, state: GameState) -> None:
    # `required_by` collects every trigger target regardless of trigger.type;
    # `kill_target_of` is an additional, narrower edge for character_death
    # triggers only — NPC view uses it to flag "kill me to advance the quest"
    # without having to re-filter required_by by trigger type.
    for qid, quest in state.quests.items():
        if quest.giver_id:
            g.add_edge(quest.giver_id, qid, "gives_quest")
        for trig in quest.triggers:
            if not trig.target_id:
                continue
            g.add_edge(trig.target_id, qid, "required_by")
            if trig.type == "character_death":
                g.add_edge(trig.target_id, qid, "kill_target_of")
        for item_id in quest.rewards.items:
            if item_id:
                g.add_edge(item_id, qid, "reward_of")


def _build_chapter_edges(g: GameGraph, state: GameState) -> None:
    for chid, chapter in state.chapters.items():
        for qid in chapter.quest_ids:
            if qid:
                g.add_edge(qid, chid, "member_of_chapter")


def _build_race_edges(g: GameGraph, state: GameState) -> None:
    for rid, race in state.races.items():
        for sid in race.racial_skill_ids:
            if sid:
                g.add_edge(sid, rid, "racial_skill_of")
