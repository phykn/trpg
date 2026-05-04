"""Build the `surroundings` dict the judge agent sees: location, entities, equipment, skills, inventory, growth, merchants."""

from ..domain.entities import (
    EQUIPMENT_SLOTS,
    Character,
    Location,
    item_kind,
)
from ..domain.state import GameState
from ..engines.growth import can_afford_level_up
from ..ontology.graph import GameGraph
from ..ontology.queries import (
    connections_of,
    equipment_of,
    inhabitants_of,
    inventory_of,
    items_in,
    known_skills_of,
    quests_given_by,
)
from ..rules import RULES


def _inventory_payload(
    state: GameState, actor: Character, graph: GameGraph
) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for item_id in inventory_of(graph, actor.id):
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
    for edge in equipment_of(graph, actor.id):
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
    for edge in known_skills_of(graph, actor.id):
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
    for cid in inhabitants_of(graph, actor.location_id):
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
        for iid in inventory_of(graph, cid):
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


def _npc_roles(
    state: GameState, actor: Character, npc: Character, graph: GameGraph
) -> list[str]:
    """Per-NPC role tags (kebab-case ASCII) so narrate can tell that a same-location NPC is *not* trade-eligible — `merchants` only carries positives, silence isn't a signal."""
    roles: list[str] = []
    aggressive_cutoff = RULES.social.hostile_aggressive_threshold
    threshold = RULES.social.trade_threshold
    if (
        npc.disposition.aggressive < aggressive_cutoff
        and npc.relations.get(actor.id, 0) >= threshold
    ):
        for iid in inventory_of(graph, npc.id):
            if state.items.get(iid) is not None:
                roles.append("merchant")
                break
    if quests_given_by(graph, npc.id):
        roles.append("quest_giver")
    return roles


def _entities_payload(
    state: GameState,
    actor_id: str,
    actor: Character,
    location: Location,
    graph: GameGraph,
) -> list[dict]:
    entities: list[dict] = [{"id": actor_id, "name": actor.name, "type": "player"}]
    for cid in inhabitants_of(graph, location.id):
        if cid == actor_id:
            continue
        char = state.characters.get(cid)
        if char is None or not char.alive:
            continue
        entry: dict = {"id": cid, "name": char.name, "type": "npc"}
        if char.gender != "none":
            entry["gender"] = char.gender
        race = state.races.get(char.race_id)
        if race is not None:
            entry["race"] = race.name
        role_label = char.role or char.job
        if role_label:
            entry["role"] = role_label
        if char.protected:
            entry["protected"] = True
        if char.relations.get(actor.id, 0) >= RULES.social.friendly_threshold:
            entry["friendly"] = True
        roles = _npc_roles(state, actor, char, graph)
        if roles:
            entry["roles"] = roles
        entities.append(entry)
    for item_id in items_in(graph, location.id):
        item = state.items.get(item_id)
        if item is None:
            continue
        entities.append({"id": item_id, "name": item.name, "type": "item"})
    for edge in connections_of(graph, location.id):
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
    """Dead NPCs (same-location bodies + off_screen=true ids surviving in turn_log) surfaced separately from `entities` so judge doesn't accept them as targets."""
    if actor.location_id is None:
        return []
    out: list[dict] = []
    seen: set[str] = set()
    for cid in inhabitants_of(graph, actor.location_id):
        if cid == actor.id:
            continue
        char = state.characters.get(cid)
        if char is None or char.alive:
            continue
        out.append(
            {
                "id": cid,
                "name": char.name,
                "inventory": _corpse_inventory_payload(state, graph, cid),
            }
        )
        seen.add(cid)
    # turn_log.target carries ids; recent_dialogue text only has names.
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


def _corpse_inventory_payload(
    state: GameState, graph: GameGraph, cid: str
) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for iid in inventory_of(graph, cid):
        if iid in seen:
            continue
        item = state.items.get(iid)
        if item is None:
            continue
        seen.add(iid)
        out.append({"id": iid, "name": item.name})
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
        graph = state.graph()
    actor = state.characters[actor_id]
    in_combat = state.combat_state is not None
    base = {
        "equipment": _equipment_payload(state, actor, graph),
        "in_combat": in_combat,
        "growth": _growth_payload(actor),
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
        "entities": _entities_payload(
            state, actor_id, actor, location, graph
        ),
        "corpses": _corpses_payload(state, actor, graph),
        "skills": _skills_payload(state, actor, graph),
        "inventory": _inventory_payload(state, actor, graph),
        "merchants": _merchants_payload(state, actor, graph),
    }


def surroundings_for_narrate_body(full: dict) -> dict:
    """body never narrates skill casts (combat_narrate does), never branches on
    equipment slots, and runs only when in_combat is False."""
    return {k: v for k, v in full.items() if k not in ("skills", "equipment", "in_combat")}


def surroundings_for_extract(full: dict) -> dict:
    """extract reads body and emits state_changes against valid ids; the rest
    tempts hallucination of changes the body didn't describe."""
    return {k: full[k] for k in ("entities", "corpses", "merchants") if k in full}
