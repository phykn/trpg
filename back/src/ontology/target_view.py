from ..domain.entities import EQUIPMENT_SLOTS
from ..state.models import GameState
from .graph import GameGraph


def build_target_view(
    state: GameState,
    graph: GameGraph,
    target_id: str,
    actor_id: str,
) -> dict | None:
    node_type = graph.get_node_type(target_id)
    if node_type == "character":
        return _build_npc_view(state, graph, target_id, actor_id)
    if node_type == "location":
        return _build_location_view(state, graph, target_id)
    if node_type == "item":
        return _build_item_view(state, graph, target_id)
    return None


def _omit_none(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


def _build_npc_view(state: GameState, graph: GameGraph, target_id: str, actor_id: str) -> dict:
    npc = state.characters[target_id]
    actor = state.characters[actor_id]

    equipped: dict[str, str] = {}
    for slot in EQUIPMENT_SLOTS:
        item_id = getattr(npc.equipment, slot)
        if item_id and item_id in state.items:
            equipped[slot] = state.items[item_id].name

    inventory: list[dict] = []
    for item_id in npc.inventory_ids:
        if item_id in state.items:
            it = state.items[item_id]
            inventory.append({"id": item_id, "name": it.name, "price": it.price})

    quest_info: list[dict] = []
    for edge in graph.get_edges(target_id, "gives_quest"):
        q = state.quests.get(edge.to_id)
        if q:
            quest_info.append({"id": q.id, "title": q.title, "status": q.status})

    return _omit_none({
        "type": "npc",
        "name": npc.name,
        "description": npc.description or None,
        "appearance": npc.appearance or None,
        "tone_hint": npc.tone_hint or None,
        "disposition": {
            "lawful": npc.disposition.lawful,
            "moral": npc.disposition.moral,
            "aggressive": npc.disposition.aggressive,
        },
        "affinity": actor.relations.get(target_id, 0),
        "hints": npc.hints or None,
        "memories": [
            {"content": m.content, "importance": m.importance, "turn": m.turn}
            for m in npc.memories
        ] or None,
        "equipment": equipped or None,
        "inventory": inventory or None,
        "quests": quest_info or None,
    })


def _build_location_view(state: GameState, graph: GameGraph, target_id: str) -> dict:
    loc = state.locations[target_id]

    items: list[dict] = []
    for item_id in loc.item_ids:
        if item_id in state.items:
            items.append({"id": item_id, "name": state.items[item_id].name})

    hidden_conns: list[dict] = []
    for conn in loc.hidden_connections:
        if conn.target_id in state.locations:
            entry: dict = {"name": state.locations[conn.target_id].name}
            if conn.difficulty:
                entry["difficulty"] = conn.difficulty
            hidden_conns.append(entry)

    quest_info: list[dict] = []
    for edge in graph.get_edges(target_id, "required_by"):
        q = state.quests.get(edge.to_id)
        if q:
            quest_info.append({"id": q.id, "title": q.title, "status": q.status})

    return _omit_none({
        "type": "location",
        "name": loc.name,
        "description": loc.description or None,
        "tags": loc.tags or None,
        "items": items or None,
        "hidden_connections": hidden_conns or None,
        "quests": quest_info or None,
    })


def _build_item_view(state: GameState, graph: GameGraph, target_id: str) -> dict:
    item = state.items[target_id]
    edges = [
        {"type": e.type, "target": e.to_id} for e in graph.get_edges(target_id)
    ]
    return _omit_none({
        "type": "item",
        "name": item.name,
        "description": item.description or None,
        "effects": item.effects.model_dump() if item.effects else None,
        "edges": edges or None,
    })
