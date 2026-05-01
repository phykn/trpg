"""Judge prompt input — `surroundings` layer.

Bundles location, entities, equipment, skills, inventory, growth, merchants and
skill candidates into the dict the judge agent sees. Payload helpers stay
private — only `build_surroundings` is exported.

Relational reads (who's at this location, what's equipped/carried, which
skills are known) go through `GameGraph` — never via `state.characters`
fullscans or direct entity-relation fields. Pure-attribute reads (HP, alive,
disposition, level, mp) still come from the entity. Phase 3 of the graph-SSOT
work, see [02-runtime.md](./02-runtime.md) §4.
"""

from ..domain.entities import (
    EQUIPMENT_SLOTS,
    Character,
    Location,
    item_kind,
)
from ..domain.state import GameState
from ..engines.growth import can_afford_level_up
from ..ontology.graph import GameGraph, build_graph
from ..rules import RULES


# --- Common helpers (NPC state tags) -----------------------------------------


def _state_tags(actor: Character, npc: Character) -> list[str]:
    tags: list[str] = []
    aff = actor.relations.get(npc.id, 0)
    threshold = RULES.social.friendly_threshold
    if aff >= threshold:
        tags.append(f"우호적(affinity {aff})")
    elif aff <= -threshold:
        tags.append(f"경계중(affinity {aff})")
    if npc.max_hp > 0:
        hp_pct = round(npc.hp / npc.max_hp * 100)
        if hp_pct < 50:
            tags.append(f"부상(hp {hp_pct}%)")
    return tags


# --- Inventory / equipment / skills / growth (actor-centric) -----------------


def _inventory_payload(
    state: GameState, actor: Character, graph: GameGraph
) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for edge in graph.get_edges(actor.id, "carries"):
        item_id = edge.to_id
        if item_id in seen:
            continue
        item = state.items.get(item_id)
        if item is None:
            continue
        seen.add(item_id)
        out.append(
            {
                "id": item_id,
                "name": item.name,
                "kind": item_kind(item),
            }
        )
    return out


def _equipment_payload(state: GameState, actor: Character, graph: GameGraph) -> dict:
    out: dict[str, dict | None] = {slot: None for slot in EQUIPMENT_SLOTS}
    for edge in graph.get_edges(actor.id, "equips"):
        item_id = edge.to_id
        slot = (edge.attrs or {}).get("slot")
        if slot is None or slot not in out:
            continue
        item = state.items.get(item_id)
        if item is None:
            continue
        out[slot] = {"id": item_id, "name": item.name}
    return out


def _skills_payload(state: GameState, actor: Character, graph: GameGraph) -> list[dict]:
    out: list[dict] = []
    for edge in graph.get_edges(actor.id, "knows_skill"):
        s = state.skills.get(edge.to_id)
        if s is None:
            continue
        # level / mp are pure entity values — graph doesn't carry them.
        if s.level > actor.level or actor.mp < s.mp_cost:
            continue
        item: dict = {"id": s.id, "name": s.name}
        if s.description:
            item["description"] = s.description
        if s.special_effect:
            item["effect"] = s.special_effect
        out.append(item)
    return out


def _growth_payload(actor: Character) -> dict:
    return {
        "can_level_up": can_afford_level_up(actor),
    }


def _skill_candidates_payload(state: GameState) -> list[dict]:
    return [
        {
            "name": s.name,
            "type": s.type,
            "target": s.target,
            "primary_stat": s.primary_stat,
            "description": s.description,
        }
        for s in state.pending_skill_candidates
    ]


# --- Location / nearby NPCs/items/connections / merchants (location-centric) -


def _merchants_payload(
    state: GameState, actor: Character, graph: GameGraph
) -> list[dict]:
    """Same-location NPCs whose affinity passes the trade threshold and who carry stock.
    Hostile seeds (bandits, beasts) are excluded by `hostile_aggressive_threshold`
    even when their relations[player] is still at the empty-dict default of 0,
    so a freshly-encountered bandit doesn't surface as a merchant just because
    they carry weapons."""
    if actor.location_id is None:
        return []
    out: list[dict] = []
    threshold = RULES.social.trade_threshold
    aggressive_cutoff = RULES.social.hostile_aggressive_threshold
    for edge in graph.get_in_edges(actor.location_id, "located_at"):
        cid = edge.from_id
        if cid == actor.id:
            continue
        npc = state.characters.get(cid)
        if npc is None or not npc.alive:
            continue
        if npc.disposition.aggressive >= aggressive_cutoff:
            continue
        if npc.relations.get(actor.id, 0) < threshold:
            continue
        stock_seen: set[str] = set()
        stock: list[dict] = []
        for carry in graph.get_edges(cid, "carries"):
            iid = carry.to_id
            if iid in stock_seen:
                continue
            item = state.items.get(iid)
            if item is None:
                continue
            stock_seen.add(iid)
            stock.append(
                {
                    "id": iid,
                    "name": item.name,
                    "price": item.price,
                    "kind": item_kind(item),
                }
            )
        if stock:
            out.append({"id": cid, "name": npc.name, "stock": stock})
    return out


def _entities_payload(
    state: GameState,
    actor_id: str,
    actor: Character,
    location: Location,
    graph: GameGraph,
) -> list[dict]:
    entities: list[dict] = [{"id": actor_id, "name": actor.name, "type": "player"}]
    for edge in graph.get_in_edges(location.id, "located_at"):
        cid = edge.from_id
        if cid == actor_id:
            continue
        char = state.characters.get(cid)
        if char is None or not char.alive:
            continue
        entry: dict = {"id": cid, "name": char.name, "type": "npc"}
        tags = _state_tags(actor, char)
        if tags:
            entry["state_tags"] = tags
        entities.append(entry)
    for edge in graph.get_in_edges(location.id, "located_in"):
        item_id = edge.from_id
        item = state.items.get(item_id)
        if item is None:
            continue
        entities.append({"id": item_id, "name": item.name, "type": "item"})
    for edge in graph.get_edges(location.id, "connects_to"):
        target_id = edge.to_id
        target_loc = state.locations.get(target_id)
        if target_loc is None:
            continue
        attrs = edge.attrs or {}
        entry = {
            "id": target_id,
            "name": target_loc.name,
            "type": "connection",
        }
        difficulty = attrs.get("difficulty")
        if difficulty:
            entry["difficulty"] = difficulty
        entities.append(entry)
    return entities


def _corpses_payload(
    state: GameState, actor: Character, graph: GameGraph
) -> list[dict]:
    """Dead NPCs surfaced for narrate so it doesn't revive them. Two sources:

    - same-location: visible as a body in the scene.
    - history-referenced (any location, marked `off_screen=true`): id appears
      in recent `turn_log.target`, so the player may still address them by
      name from somewhere else. Without this, narrate loses the death
      signal the moment the player walks away and hallucinates the dead
      NPC speaking again from `recent_dialogue` text.

    Surfaced separately from `entities` so judge semantics doesn't accept
    them as combat/buy/sell targets.
    """
    if actor.location_id is None:
        return []
    out: list[dict] = []
    seen: set[str] = set()
    for edge in graph.get_in_edges(actor.location_id, "located_at"):
        cid = edge.from_id
        if cid == actor.id:
            continue
        char = state.characters.get(cid)
        if char is None or char.alive:
            continue
        out.append({"id": cid, "name": char.name})
        seen.add(cid)
    # turn_log's structured `target` field is the only way to recover ids
    # from history without fuzzy-matching narrator prose. recent_dialogue
    # text mentions names but not ids.
    for entry in state.turn_log:
        tid = entry.target
        if tid is None or tid == actor.id or tid in seen:
            continue
        ch = state.characters.get(tid)
        if ch is None or ch.alive:
            continue
        out.append({"id": tid, "name": ch.name, "off_screen": True})
        seen.add(tid)
    return out


def _location_payload(location: Location) -> dict:
    out: dict = {
        "id": location.id,
        "name": location.name,
        "description": location.description,
    }
    if location.tags:
        out["tags"] = location.tags
    if location.weather:
        out["weather"] = location.weather
    if location.difficulty:
        out["difficulty"] = location.difficulty
    return out


# --- Entry point (the dict the judge sees) -----------------------------------


def build_surroundings(
    state: GameState,
    actor_id: str,
    graph: GameGraph | None = None,
) -> dict:
    """Assemble the surroundings payload. `graph` is the relational SSOT —
    callers that already built one (flow entry points) should pass it; tests
    and ad-hoc callers can omit and we'll build internally.
    """
    if graph is None:
        graph = build_graph(state)
    actor = state.characters[actor_id]
    in_combat = state.combat_state is not None
    base = {
        "equipment": _equipment_payload(state, actor, graph),
        "in_combat": in_combat,
        "growth": _growth_payload(actor),
        "skill_candidates": _skill_candidates_payload(state),
        "recent_npc": state.recent_npc_id(actor_id),
    }
    if not actor.location_id or actor.location_id not in state.locations:
        return {
            **base,
            "location": None,
            "entities": [],
            "corpses": [],
            "skills": [],
            "inventory": [],
            "merchants": [],
        }
    location = state.locations[actor.location_id]
    return {
        **base,
        "location": _location_payload(location),
        "entities": _entities_payload(state, actor_id, actor, location, graph),
        "corpses": _corpses_payload(state, actor, graph),
        "skills": _skills_payload(state, actor, graph),
        "inventory": _inventory_payload(state, actor, graph),
        "merchants": _merchants_payload(state, actor, graph),
    }
