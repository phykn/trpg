"""Target view — what narrate sees about the entity the player addressed.

Phase 4: traverses the graph 2 hops so prompts can phrase quests in
context. NPC view: from the NPC, 1-hop along `gives_quest` to a quest,
2-hop into the quest's kill targets / locations / items / rewards. Same
for `kill_target_of` so an NPC that the player must kill flags it on
their view too. Location view: 1-hop along `required_by` to a quest,
2-hop to the quest's giver / rewards. Item view: resolves the raw 1-hop
edge ids to names so narrate doesn't see bare ids in `unlocks` /
`reward_of`.
"""

from ..domain.state import GameState
from .graph import GameGraph


def build_target_view(
    state: GameState,
    graph: GameGraph,
    target_id: str,
    actor_id: str,
) -> dict | None:
    node_type = graph.get_node_type(target_id)
    if node_type == "character":
        # Dead NPCs return a minimal dead-marker payload — name + alive=false.
        # We don't expose memories/inventory (no live persona to render), but
        # narrate still needs the explicit "this target is dead" signal so it
        # won't revive them as a passerby. This is the belt-and-suspenders
        # pair to surroundings.corpses: corpses covers "player mentions a
        # dead NPC by name", target_view covers "judge routed
        # targets=[corpse_id] past the Corpse rule".
        npc = state.characters.get(target_id)
        if npc is not None and not npc.alive:
            return {
                "type": "npc",
                "id": target_id,
                "name": npc.name,
                "alive": False,
            }
        return _build_npc_view(state, graph, target_id, actor_id)
    if node_type == "location":
        return _build_location_view(state, graph, target_id)
    if node_type == "item":
        return _build_item_view(state, graph, target_id)
    return None


def _omit_none(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


# --- 2-hop helpers ----------------------------------------------------------


def _resolve_neighbor(state: GameState, graph: GameGraph, node_id: str) -> dict | None:
    """Turn a graph node id into a `{id, kind, name}` dict that the prompt
    can render. Returns None for unknown ids — graph nodes that point at a
    missing entity (stale edge). Quest nodes return `{id, kind, title}`."""
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
    state: GameState, graph: GameGraph, qid: str, *, include_giver: bool
) -> dict | None:
    """Resolve a quest into a prompt-ready dict via 1-hop in-edges:
    - `kill_targets`: characters with a `character_death` trigger
    - `triggers`: other trigger targets (locations to enter, items to use)
    - `rewards`: items handed out on completion
    - `giver`: the NPC who gave it (only when `include_giver=True` —
      omitted for NPC view because the NPC already knows it's the giver,
      surfaced for location view so narrate can say "이 장소를 가야 하는
      이유는 X 영감의 부탁이오")
    """
    q = state.quests.get(qid)
    if q is None:
        return None
    out: dict = {"id": q.id, "title": q.title, "status": q.status}

    kill_set: set[str] = set()
    kill_targets: list[dict] = []
    for e in graph.get_in_edges(qid, "kill_target_of"):
        nb = _resolve_neighbor(state, graph, e.from_id)
        if nb is None:
            continue
        kill_set.add(e.from_id)
        kill_targets.append({"id": nb["id"], "name": nb["name"]})
    if kill_targets:
        out["kill_targets"] = kill_targets

    triggers: list[dict] = []
    for e in graph.get_in_edges(qid, "required_by"):
        if e.from_id in kill_set:
            # Already surfaced as a kill_target — don't duplicate.
            continue
        nb = _resolve_neighbor(state, graph, e.from_id)
        if nb is not None:
            triggers.append(nb)
    if triggers:
        out["triggers"] = triggers

    rewards: list[dict] = []
    for e in graph.get_in_edges(qid, "reward_of"):
        item = state.items.get(e.from_id)
        if item is not None:
            rewards.append({"id": e.from_id, "name": item.name})
    if rewards:
        out["rewards"] = rewards

    if include_giver:
        for e in graph.get_in_edges(qid, "gives_quest"):
            giver = state.characters.get(e.from_id)
            if giver is not None:
                out["giver"] = {"id": e.from_id, "name": giver.name}
                break

    return out


def _build_npc_view(
    state: GameState, graph: GameGraph, target_id: str, actor_id: str
) -> dict:
    npc = state.characters[target_id]

    # Race: relation through graph (belongs_to_race), then attribute lookup
    # for the race's display name/description.
    race_payload = None
    for edge in graph.get_edges(target_id, "belongs_to_race"):
        race = state.races.get(edge.to_id)
        if race is not None:
            race_payload = _omit_none(
                {"name": race.name, "description": race.description or None}
            )
            break

    equipped: dict[str, str] = {}
    for edge in graph.get_edges(target_id, "equips"):
        slot = (edge.attrs or {}).get("slot")
        if slot is None:
            continue
        item = state.items.get(edge.to_id)
        if item is None:
            continue
        equipped[slot] = item.name

    inventory: list[dict] = []
    inv_seen: set[str] = set()
    for edge in graph.get_edges(target_id, "carries"):
        iid = edge.to_id
        if iid in inv_seen:
            continue
        item = state.items.get(iid)
        if item is None:
            continue
        inv_seen.add(iid)
        inventory.append({"id": iid, "name": item.name, "price": item.price})

    # Quests this NPC gives — 2-hop into kill_targets / triggers / rewards.
    quests_given: list[dict] = []
    for edge in graph.get_edges(target_id, "gives_quest"):
        payload = _quest_payload(state, graph, edge.to_id, include_giver=False)
        if payload is not None:
            quests_given.append(payload)

    # Quests this NPC is the kill target of — flagged so narrate knows
    # "killing me advances something". Different list from quests_given so
    # the LLM doesn't conflate "this NPC offers a job" with "this NPC IS the
    # job."
    quests_kill_target: list[dict] = []
    for edge in graph.get_edges(target_id, "kill_target_of"):
        q = state.quests.get(edge.to_id)
        if q is None:
            continue
        item: dict = {"id": q.id, "title": q.title, "status": q.status}
        for ge in graph.get_in_edges(edge.to_id, "gives_quest"):
            giver = state.characters.get(ge.from_id)
            if giver is not None:
                item["giver"] = {"id": ge.from_id, "name": giver.name}
                break
        quests_kill_target.append(item)

    return _omit_none(
        {
            "type": "npc",
            "name": npc.name,
            "race": race_payload,
            "description": npc.description or None,
            "appearance": npc.appearance or None,
            "gender": npc.gender if npc.gender != "none" else None,
            "tone_hint": npc.tone_hint or None,
            "memories": [
                {"content": m.content, "importance": m.importance} for m in npc.memories
            ]
            or None,
            "equipment": equipped or None,
            "inventory": inventory or None,
            "quests_given": quests_given or None,
            "quests_kill_target": quests_kill_target or None,
        }
    )


def _build_location_view(state: GameState, graph: GameGraph, target_id: str) -> dict:
    loc = state.locations[target_id]

    items: list[dict] = []
    for edge in graph.get_in_edges(target_id, "located_in"):
        item = state.items.get(edge.from_id)
        if item is not None:
            items.append({"id": edge.from_id, "name": item.name})

    # Quests that require entering this location — 2-hop adds the giver so
    # narrate can phrase "이 장소에 가야 하는 이유는 X 영감의 부탁이오".
    quests: list[dict] = []
    for edge in graph.get_edges(target_id, "required_by"):
        payload = _quest_payload(state, graph, edge.to_id, include_giver=True)
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
    """Item view: surface the item itself + its outgoing relations as
    name-resolved lists. Raw `edges` array is gone — narrate prompt forbids
    raw ids and we control the ids that leak by resolving them here."""
    item = state.items[target_id]

    unlocks: list[dict] = []
    for edge in graph.get_edges(target_id, "unlocks"):
        loc = state.locations.get(edge.to_id)
        if loc is not None:
            unlocks.append({"id": edge.to_id, "name": loc.name})

    reward_of: list[dict] = []
    for edge in graph.get_edges(target_id, "reward_of"):
        q = state.quests.get(edge.to_id)
        if q is not None:
            reward_of.append({"id": edge.to_id, "title": q.title})

    located_in: list[dict] = []
    for edge in graph.get_edges(target_id, "located_in"):
        loc = state.locations.get(edge.to_id)
        if loc is not None:
            located_in.append({"id": edge.to_id, "name": loc.name})

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
