"""Judge prompt input — `surroundings` layer.

Bundles location, entities, equipment, skills, inventory, growth, merchants and
skill candidates into the dict the judge agent sees. Payload helpers stay
private — only `build_surroundings` is exported.
"""
from collections import Counter

from ..domain.entities import (
    EQUIPMENT_SLOTS,
    ArmorEffect,
    Character,
    ConsumableEffect,
    Location,
    WeaponEffect,
)
from ..domain.state import GameState
from ..engines.growth import can_afford_level_up, xp_for_next_level
from ..rules import RULES


# --- Common helpers (NPC state tags / item kind classification) --------------


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


def _item_kind(item) -> str:
    eff = item.effects
    if isinstance(eff, ConsumableEffect):
        return "consumable"
    if isinstance(eff, WeaponEffect):
        return "weapon"
    if isinstance(eff, ArmorEffect):
        return "armor"
    if item.on_use:
        return "trigger"
    return "misc"


# --- Inventory / equipment / skills / growth (actor-centric) -----------------


def _inventory_payload(state: GameState, actor: Character) -> list[dict]:
    counts: Counter[str] = Counter(actor.inventory_ids)
    out: list[dict] = []
    for item_id, qty in counts.items():
        item = state.items.get(item_id)
        if item is None:
            continue
        entry: dict = {
            "id": item_id,
            "name": item.name,
            "qty": qty,
            "kind": _item_kind(item),
        }
        if isinstance(item.effects, ConsumableEffect):
            entry["effect"] = item.effects.effect
        if item.description:
            entry["description"] = item.description
        out.append(entry)
    return out


def _equipment_payload(state: GameState, actor: Character) -> dict:
    out: dict[str, dict | None] = {slot: None for slot in EQUIPMENT_SLOTS}
    for slot, item_id in actor.equipment.equipped_items():
        if item_id in state.items:
            out[slot] = {"id": item_id, "name": state.items[item_id].name}
    return out


def _skills_payload(state: GameState, actor: Character) -> list[dict]:
    out: list[dict] = []
    for source, ids in (
        ("racial", actor.racial_skill_ids),
        ("learned", actor.learned_skill_ids),
    ):
        for sid in ids:
            s = state.skills.get(sid)
            if s is None:
                continue
            if s.level > actor.level or actor.mp < s.mp_cost:
                continue
            item: dict = {
                "id": s.id,
                "name": s.name,
                "type": s.type,
                "target": s.target,
                "source": source,
            }
            if s.description:
                item["description"] = s.description
            if s.special_effect:
                item["effect"] = s.special_effect
            out.append(item)
    return out


def _growth_payload(actor: Character) -> dict:
    return {
        "level": actor.level,
        "xp_pool": actor.xp_pool,
        "xp_needed": xp_for_next_level(actor.level),
        "can_level_up": can_afford_level_up(actor),
    }


def _recent_npc_id(state: GameState, actor_id: str) -> str | None:
    """Most recently addressed NPC at this location — anchors pronoun /
    follow-up inputs ('한 번만 더 말해봐', '그래서?') to the same NPC instead
    of letting the judge drift to a different same-location character.
    Returns None if no recent target exists or it isn't an alive same-location
    NPC.
    """
    if not state.turn_log:
        return None
    actor = state.characters.get(actor_id)
    actor_loc = actor.location_id if actor is not None else None
    for entry in reversed(state.turn_log):
        tid = entry.target
        if tid is None or tid == actor_id:
            continue
        npc = state.characters.get(tid)
        if npc is None or not npc.alive:
            continue
        if actor_loc is not None and npc.location_id != actor_loc:
            continue
        return tid
    return None


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


def _merchants_payload(state: GameState, actor: Character) -> list[dict]:
    """Same-location NPCs whose affinity passes the trade threshold and who carry stock."""
    if actor.location_id is None:
        return []
    out: list[dict] = []
    threshold = RULES.social.trade_threshold
    for cid, npc in state.characters.items():
        if cid == actor.id or npc.location_id != actor.location_id:
            continue
        if not npc.alive or not npc.inventory_ids:
            continue
        if npc.relations.get(actor.id, 0) < threshold:
            continue
        stock: list[dict] = []
        for iid in set(npc.inventory_ids):
            item = state.items.get(iid)
            if item is None:
                continue
            stock.append({
                "id": iid,
                "name": item.name,
                "price": item.price,
                "kind": _item_kind(item),
            })
        if stock:
            out.append({"id": cid, "name": npc.name, "stock": stock})
    return out


def _entities_payload(
    state: GameState, actor_id: str, actor: Character, location: Location
) -> list[dict]:
    entities: list[dict] = [{"id": actor_id, "name": actor.name, "type": "player"}]
    for cid, char in state.characters.items():
        if cid == actor_id or char.location_id != actor.location_id:
            continue
        if not char.alive:
            continue
        entry: dict = {"id": cid, "name": char.name, "type": "npc"}
        tags = _state_tags(actor, char)
        if tags:
            entry["state_tags"] = tags
        entities.append(entry)
    for item_id in location.item_ids:
        if item_id in state.items:
            entities.append(
                {"id": item_id, "name": state.items[item_id].name, "type": "item"}
            )
    for conn in location.connections:
        if conn.target_id not in state.locations:
            continue
        entry = {
            "id": conn.target_id,
            "name": state.locations[conn.target_id].name,
            "type": "connection",
        }
        if conn.difficulty:
            entry["difficulty"] = conn.difficulty
        entities.append(entry)
    return entities


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


def build_surroundings(state: GameState, actor_id: str) -> dict:
    actor = state.characters[actor_id]
    in_combat = state.combat_state is not None
    base = {
        "equipment": _equipment_payload(state, actor),
        "in_combat": in_combat,
        "growth": _growth_payload(actor),
        "skill_candidates": _skill_candidates_payload(state),
        "recent_npc": _recent_npc_id(state, actor_id),
    }
    if not actor.location_id or actor.location_id not in state.locations:
        return {
            **base,
            "location": None,
            "entities": [],
            "skills": [],
            "inventory": [],
            "merchants": [],
        }
    location = state.locations[actor.location_id]
    return {
        **base,
        "location": _location_payload(location),
        "entities": _entities_payload(state, actor_id, actor, location),
        "skills": _skills_payload(state, actor),
        "inventory": _inventory_payload(state, actor),
        "merchants": _merchants_payload(state, actor),
    }
