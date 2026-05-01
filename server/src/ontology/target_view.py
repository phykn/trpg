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
    """`grade` gates the secret slots: on a failed roll
    (`is_secret_masked_grade(grade)`) NPC inner state (`tone_hint`,
    `memories`) and quest reward detail are dropped before narrate sees
    them. Other grades / non-roll calls leave the view untouched."""
    masked = is_secret_masked_grade(grade)
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
        return _build_npc_view(state, graph, target_id, actor_id, masked=masked)
    if node_type == "location":
        return _build_location_view(state, graph, target_id, masked=masked)
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
    state: GameState,
    graph: GameGraph,
    qid: str,
    *,
    include_giver: bool,
    masked: bool = False,
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

    # Reward detail is a "secret" surface for the failure-grade mask: a botched
    # social/investigation roll shouldn't let the LLM surface what the NPC
    # would have given on success.
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

    # Race: relation through graph (belongs_to_race), then attribute lookup
    # for the race's display name/description.
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

    # Quests this NPC gives — 2-hop into kill_targets / triggers / rewards.
    quests_given: list[dict] = []
    for qid in quests_given_by(graph, target_id):
        payload = _quest_payload(state, graph, qid, include_giver=False, masked=masked)
        if payload is not None:
            quests_given.append(payload)

    # Quests this NPC is the kill target of — flagged so narrate knows
    # "killing me advances something". Different list from quests_given so
    # the LLM doesn't conflate "this NPC offers a job" with "this NPC IS the
    # job."
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

    # Inner-state slots blocked at the data layer when narrate is rendering a
    # failed roll: tone_hint exposes the NPC's true disposition; memories
    # carry past secrets the player hasn't earned this turn. The narrate
    # prompt also forbids leaking these on failure, but the LLM drifts —
    # keeping the data out of the prompt is the only hard block.
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

    # Quests that require entering this location — 2-hop adds the giver so
    # narrate can phrase "이 장소에 가야 하는 이유는 X 영감의 부탁이오".
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
    """Item view: surface the item itself + its outgoing relations as
    name-resolved lists. Raw `edges` array is gone — narrate prompt forbids
    raw ids and we control the ids that leak by resolving them here."""
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
