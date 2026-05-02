from ..domain.state import GameState
from ..domain.types import is_secret_masked_grade
from .graph import GameGraph
from .queries import (
    container_of,
    equipment_of,
    giver_of,
    inventory_of,
    items_in,
    kill_targets_of,
    locations_unlocked_by,
    quests_given_by,
    quests_killing,
    quests_requiring,
    quests_rewarding,
    race_of,
    reward_items_of,
    trigger_targets_of,
)


def build_target_view(
    state: GameState,
    graph: GameGraph,
    target_id: str,
    actor_id: str,
    *,
    grade: str | None = None,
) -> dict | None:
    """`grade` masks NPC inner state (`tone_hint`, `memories`) and quest reward detail on failed rolls."""
    masked = is_secret_masked_grade(grade)
    node_type = graph.get_node_type(target_id)
    if node_type == "character":
        npc = state.characters.get(target_id)
        if npc is not None and not npc.alive:
            return {
                "type": "npc",
                "id": target_id,
                "name": npc.name,
                "alive": False,
                "inventory": _corpse_inventory(state, graph, target_id),
            }
        return _build_npc_view(state, graph, target_id, actor_id, masked=masked)
    if node_type == "location":
        return _build_location_view(state, graph, target_id, masked=masked)
    if node_type == "item":
        return _build_item_view(state, graph, target_id)
    return None


def _omit_none(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


def _corpse_inventory(state: GameState, graph: GameGraph, target_id: str) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for iid in inventory_of(graph, target_id):
        if iid in seen:
            continue
        item = state.items.get(iid)
        if item is None:
            continue
        seen.add(iid)
        out.append({"id": iid, "name": item.name})
    return out


def _resolve_neighbor(state: GameState, graph: GameGraph, node_id: str) -> dict | None:
    """Resolve a node id to `{id, kind, name}` (quests return `title`). None for stale ids."""
    nt = graph.get_node_type(node_id)
    if nt == "character":
        c = state.characters.get(node_id)
        return {"id": node_id, "kind": "character", "name": c.name} if c else None
    if nt == "location":
        loc = state.locations.get(node_id)
        return {"id": node_id, "kind": "location", "name": loc.name} if loc else None
    if nt == "item":
        item = state.items.get(node_id)
        return {"id": node_id, "kind": "item", "name": item.name} if item else None
    if nt == "quest":
        q = state.quests.get(node_id)
        return {"id": node_id, "kind": "quest", "title": q.title} if q else None
    return None


def _quest_payload(
    state: GameState,
    graph: GameGraph,
    qid: str,
    *,
    include_giver: bool,
    masked: bool = False,
) -> dict | None:
    """Resolve a quest to `{id, title, status, kill_targets?, triggers?, rewards?, giver?}` via 1-hop in-edges."""
    q = state.quests.get(qid)
    if q is None:
        return None
    out: dict = {"id": q.id, "title": q.title, "status": q.status}

    kill_set: set[str] = set()
    kill_targets: list[dict] = []
    for cid in kill_targets_of(graph, qid):
        nb = _resolve_neighbor(state, graph, cid)
        if nb is None:
            continue
        kill_set.add(cid)
        kill_targets.append({"id": nb["id"], "name": nb["name"]})
    if kill_targets:
        out["kill_targets"] = kill_targets

    triggers: list[dict] = []
    for tid in trigger_targets_of(graph, qid):
        if tid in kill_set:
            # Already surfaced as a kill_target — don't duplicate.
            continue
        nb = _resolve_neighbor(state, graph, tid)
        if nb is not None:
            triggers.append(nb)
    if triggers:
        out["triggers"] = triggers

    # Reward detail is masked on failed rolls so the LLM can't leak success-only payouts.
    if not masked:
        rewards: list[dict] = []
        for iid in reward_items_of(graph, qid):
            item = state.items.get(iid)
            if item is not None:
                rewards.append({"id": iid, "name": item.name})
        if rewards:
            out["rewards"] = rewards

    if include_giver:
        gid = giver_of(graph, qid)
        if gid is not None:
            giver = state.characters.get(gid)
            if giver is not None:
                out["giver"] = {"id": gid, "name": giver.name}

    return out


def _build_npc_view(
    state: GameState,
    graph: GameGraph,
    target_id: str,
    actor_id: str,
    *,
    masked: bool = False,
) -> dict:
    npc = state.characters[target_id]

    race_payload = None
    race_id = race_of(graph, target_id)
    if race_id is not None:
        race = state.races.get(race_id)
        if race is not None:
            race_payload = _omit_none(
                {"name": race.name, "description": race.description or None}
            )

    equipped: dict[str, str] = {}
    for edge in equipment_of(graph, target_id):
        slot = (edge.attrs or {}).get("slot")
        if slot is None:
            continue
        item = state.items.get(edge.to_id)
        if item is None:
            continue
        equipped[slot] = item.name

    inventory: list[dict] = []
    inv_seen: set[str] = set()
    for iid in inventory_of(graph, target_id):
        if iid in inv_seen:
            continue
        item = state.items.get(iid)
        if item is None:
            continue
        inv_seen.add(iid)
        inventory.append({"id": iid, "name": item.name, "price": item.price})

    quests_given: list[dict] = []
    for qid in quests_given_by(graph, target_id):
        payload = _quest_payload(state, graph, qid, include_giver=False, masked=masked)
        if payload is not None:
            quests_given.append(payload)

    # Separate list from quests_given so the LLM doesn't conflate "offers a job" with "IS the job".
    quests_kill_target: list[dict] = []
    for qid in quests_killing(graph, target_id):
        q = state.quests.get(qid)
        if q is None:
            continue
        item: dict = {"id": q.id, "title": q.title, "status": q.status}
        gid = giver_of(graph, qid)
        if gid is not None:
            giver = state.characters.get(gid)
            if giver is not None:
                item["giver"] = {"id": gid, "name": giver.name}
        quests_kill_target.append(item)

    # Hard block at the data layer: prompt rules also forbid leaking these on failure but the LLM drifts.
    tone_hint = None if masked else (npc.tone_hint or None)
    memories = (
        None
        if masked
        else (
            [{"content": m.content, "importance": m.importance} for m in npc.memories]
            or None
        )
    )
    return _omit_none(
        {
            "type": "npc",
            "name": npc.name,
            "race": race_payload,
            "description": npc.description or None,
            "appearance": npc.appearance or None,
            "gender": npc.gender if npc.gender != "none" else None,
            "tone_hint": tone_hint,
            "memories": memories,
            "equipment": equipped or None,
            "inventory": inventory or None,
            "quests_given": quests_given or None,
            "quests_kill_target": quests_kill_target or None,
        }
    )


def _build_location_view(
    state: GameState, graph: GameGraph, target_id: str, *, masked: bool = False
) -> dict:
    loc = state.locations[target_id]

    items: list[dict] = []
    for iid in items_in(graph, target_id):
        item = state.items.get(iid)
        if item is not None:
            items.append({"id": iid, "name": item.name})

    # 2-hop adds the giver so narrate can phrase "이 장소에 가야 하는 이유는 X 영감의 부탁이오".
    quests: list[dict] = []
    for qid in quests_requiring(graph, target_id):
        payload = _quest_payload(state, graph, qid, include_giver=True, masked=masked)
        if payload is not None:
            quests.append(payload)

    return _omit_none(
        {
            "type": "location",
            "name": loc.name,
            "description": loc.description or None,
            "tags": loc.tags or None,
            "items": items or None,
            "quests": quests or None,
        }
    )


def _build_item_view(state: GameState, graph: GameGraph, target_id: str) -> dict:
    """Outgoing relations name-resolved here — narrate prompt forbids raw ids."""
    item = state.items[target_id]

    unlocks: list[dict] = []
    for lid in locations_unlocked_by(graph, target_id):
        loc = state.locations.get(lid)
        if loc is not None:
            unlocks.append({"id": lid, "name": loc.name})

    reward_of: list[dict] = []
    for qid in quests_rewarding(graph, target_id):
        q = state.quests.get(qid)
        if q is not None:
            reward_of.append({"id": qid, "title": q.title})

    located_in: list[dict] = []
    container_id = container_of(graph, target_id)
    if container_id is not None:
        loc = state.locations.get(container_id)
        if loc is not None:
            located_in.append({"id": container_id, "name": loc.name})

    return _omit_none(
        {
            "type": "item",
            "name": item.name,
            "description": item.description or None,
            "effects": item.effects.model_dump() if item.effects else None,
            "unlocks": unlocks or None,
            "reward_of": reward_of or None,
            "located_in": located_in or None,
        }
    )
