"""FrontState builder — `to_front_state(state)` returns the flat dict the
client renders. Korean dates, durations, composed strings, and conditional
labels are all built here. Story graph projection lives in
`story_graph.py`; shared label helpers live in `labels.py`."""

from collections import Counter
from typing import Literal

from src.game.domain.clock import day_phase
from src.game.domain.entities import EQUIPMENT_SLOTS
from src.game.domain.memory import PendingCheck
from src.game.domain.state import GameState
from src.game.engines.growth import can_afford_level_up, xp_for_next_level
from src.game.ontology.graph import GameGraph
from src.game.ontology.queries import (
    companions_of,
    connections_of,
    equipment_of,
    inhabitants_of,
    inventory_of,
    known_skills_of,
)
from src.game.rules import RULES
from src.locale import render
from src.locale.labels import gender_label
from .labels import (
    difficulty_badge,
    giver_with_location_label,
    race_job_label,
    risk_payload,
    stat_label,
    stats_payload,
)
from .models import (
    CombatBadgePayload,
    CombatEnemy,
    DifficultyBadge,
    Equipment,
    EquipItem,
    HeroPayload,
    InventoryItem,
    PlacePayload,
    PlaceSurrounding,
    PlaceTarget,
    QuestPayload,
    QuestRewards,
    RiskBadge,
    StatEntry,
    SubjectPayload,
)
from .story_graph import to_story_graph


__all__ = [
    "stat_label",
    "to_hero",
    "to_subject",
    "to_quest",
    "to_place",
    "to_combat",
    "pending_check_to_front",
    "to_front_state",
]


def _build_hero_payload(state: GameState, graph: GameGraph) -> HeroPayload:
    """Typed wire model for the `hero` state slot. SSOT for to_hero
    dict construction. Pulls equipment/inventory/skills/companions via
    ontology queries, stats via stats_payload, level math via growth."""
    p = state.characters[state.player_id]

    equipped: dict[str, EquipItem | None] = {slot: None for slot in EQUIPMENT_SLOTS}
    for edge in equipment_of(graph, p.id):
        slot = (edge.attrs or {}).get("slot")
        if slot is None or slot not in equipped:
            continue
        item = state.items.get(edge.to_id)
        if item is None:
            continue
        equipped[slot] = EquipItem(name=item.name)

    counts: Counter[str] = Counter(inventory_of(graph, p.id))
    for edge in equipment_of(graph, p.id):
        item_id = edge.to_id
        counts[item_id] -= 1
        if counts[item_id] <= 0:
            del counts[item_id]
    inventory: list[InventoryItem] = [InventoryItem(name=f"금화({p.gold})", qty=1)]
    inventory.extend(
        InventoryItem(name=state.items[item_id].name, qty=qty)
        for item_id, qty in counts.items()
        if item_id in state.items
    )

    skills: list[str] = []
    seen: set[str] = set()
    for edge in known_skills_of(graph, p.id):
        sid = edge.to_id
        if sid in seen:
            continue
        skill = state.skills.get(sid)
        if skill is None:
            continue
        seen.add(sid)
        skills.append(skill.name)

    companions: list[str] = []
    for cid in companions_of(graph, p.id):
        if cid not in state.characters:
            continue
        c = state.characters[cid]
        companions.append(f"{c.name} ({race_job_label(state, graph, c)})")

    return HeroPayload(
        name=p.name,
        alive=p.alive,
        race_job=race_job_label(state, graph, p),
        gender=gender_label(p.gender),
        level=p.level,
        exp=p.xp_pool,
        exp_max=xp_for_next_level(p.level),
        can_level_up=can_afford_level_up(p),
        hp=p.hp,
        hp_max=p.max_hp,
        mp=p.mp,
        mp_max=p.max_mp,
        revive_coins=p.revive_coins,
        revive_coins_max=RULES.death.revive_coins,
        gold=p.gold,
        stats=[StatEntry(**row) for row in stats_payload(p.stats)],
        equipment=Equipment(**equipped),
        inventory=inventory,
        status=list(p.status),
        skills=skills,
        companions=companions,
    )


def _build_subject_payload(state: GameState, graph: GameGraph) -> SubjectPayload | None:
    """Typed wire model for the `subject` state slot. Returns None when
    no subject is active or the active id no longer resolves. `known` =
    appearance + hints + player memories; gold pseudo-row at inventory[0]."""
    if state.active_subject_id is None:
        return None
    sid = state.active_subject_id
    if sid not in state.characters:
        return None
    s = state.characters[sid]
    player = state.characters[state.player_id]

    known: list[str] = [s.appearance] if s.appearance and s.alive else []
    known += list(s.hints)
    known += [m.content for m in player.memories if m.target_id == sid]

    equipped: dict[str, EquipItem | None] = {slot: None for slot in EQUIPMENT_SLOTS}
    for edge in equipment_of(graph, s.id):
        slot = (edge.attrs or {}).get("slot")
        if slot is None or slot not in equipped:
            continue
        item = state.items.get(edge.to_id)
        if item is None:
            continue
        equipped[slot] = EquipItem(name=item.name)

    counts: Counter[str] = Counter(inventory_of(graph, s.id))
    for edge in equipment_of(graph, s.id):
        item_id = edge.to_id
        counts[item_id] -= 1
        if counts[item_id] <= 0:
            del counts[item_id]
    inventory: list[InventoryItem] = [InventoryItem(name=f"금화({s.gold})", qty=1)]
    inventory.extend(
        InventoryItem(name=state.items[item_id].name, qty=qty)
        for item_id, qty in counts.items()
        if item_id in state.items
    )

    skills: list[str] = []
    seen: set[str] = set()
    for edge in known_skills_of(graph, s.id):
        skill_id = edge.to_id
        if skill_id in seen:
            continue
        skill = state.skills.get(skill_id)
        if skill is None:
            continue
        seen.add(skill_id)
        skills.append(skill.name)

    return SubjectPayload(
        name=s.name,
        alive=s.alive,
        role=s.role,
        race_job=race_job_label(state, graph, s),
        gender=gender_label(s.gender),
        trust=s.relations.get(state.player_id, 0),
        known=known,
        level=s.level,
        hp=s.hp,
        hp_max=s.max_hp,
        stats=[StatEntry(**row) for row in stats_payload(s.stats)],
        equipment=Equipment(**equipped),
        inventory=inventory,
        skills=skills,
    )


def _build_quest_payload(state: GameState, graph: GameGraph) -> QuestPayload | None:
    """Typed wire model for the `quest` state slot. Returns None when no
    quest is active. Goals from triggers, progress label from triggers_met
    counts, action list from status."""
    if state.active_quest_id is None:
        return None
    qid = state.active_quest_id
    if qid not in state.quests:
        return None
    q = state.quests[qid]

    giver_name = giver_with_location_label(state, graph, qid) or qid
    goals = [t.name for t in q.triggers]
    total = len(q.triggers)
    done = sum(1 for met in q.triggers_met[:total] if met)
    if total == 0:
        progress_label = ""
    elif done >= total:
        progress_label = "✓"
    else:
        progress_label = f"{done}/{total}"

    actions: list[Literal["accept", "abandon"]] = []
    if q.status == "pending":
        actions.append("accept")
    elif q.status == "active":
        actions.append("abandon")

    badge = difficulty_badge(q.difficulty)
    return QuestPayload(
        id=qid,
        title=q.title,
        summary=q.summary,
        giver=giver_name,
        difficulty=DifficultyBadge(label=badge["label"], tone=badge["tone"]),
        goals=goals,
        progress_label=progress_label,
        rewards=QuestRewards(gold=q.rewards.gold, exp=q.rewards.exp),
        status=q.status,
        actions=actions,
    )


def _build_place_payload(state: GameState, graph: GameGraph) -> PlacePayload | None:
    """Typed wire model for the `place` state slot. Returns None when the
    player has no location. Surroundings via connections_of, targets via
    inhabitants_of, blurb fallback chain, day_phase via clock + render."""
    p = state.characters[state.player_id]
    player_loc_id = p.location_id
    if player_loc_id is None or player_loc_id not in state.locations:
        return None
    loc = state.locations[player_loc_id]

    surroundings: list[PlaceSurrounding] = []
    for edge in connections_of(graph, player_loc_id):
        target = state.locations.get(edge.to_id)
        if target is None:
            continue
        attrs = edge.attrs or {}
        difficulty_label: str | None = (
            render(f"tier.{d}", "ko") if (d := attrs.get("difficulty")) else None
        )
        risk = risk_payload(target.sleep_risk)
        surroundings.append(
            PlaceSurrounding(
                name=target.name,
                blurb=target.description,
                difficulty=difficulty_label,
                risk=RiskBadge(label=risk["label"], tone=risk["tone"]),
            )
        )

    targets: list[PlaceTarget] = []
    for cid in inhabitants_of(graph, player_loc_id):
        if cid == state.player_id:
            continue
        c = state.characters.get(cid)
        if c is None:
            continue
        blurb = "죽음" if not c.alive else (c.appearance or c.description)
        targets.append(
            PlaceTarget(
                name=c.name,
                level=c.level,
                race_job=race_job_label(state, graph, c),
                gender=gender_label(c.gender),
                blurb=blurb,
                trust=c.relations.get(state.player_id, 0),
            )
        )

    risk = risk_payload(loc.sleep_risk)
    return PlacePayload(
        name=loc.name,
        description=loc.description,
        day_phase=render(f"phase.{day_phase(state.turn_count)}", "ko"),
        weather=list(loc.weather),
        surroundings=surroundings,
        targets=targets,
        risk=RiskBadge(label=risk["label"], tone=risk["tone"]),
    )


def _build_combat_badge_payload(state: GameState) -> CombatBadgePayload | None:
    """Typed wire model for the `combat` state slot. Returns None when
    there's no active combat or turn_order is empty. Composes the Korean
    `turn_label` ("내 차례" or "{name} 차례") server-side."""
    cs = state.combat_state
    if cs is None or not cs.turn_order:
        return None
    current_id = cs.turn_order[cs.current_turn]
    current = state.characters.get(current_id)
    actor_name = current.name if current else current_id
    turn_label = "내 차례" if current_id == state.player_id else f"{actor_name} 차례"

    enemies: list[CombatEnemy] = []
    for eid in cs.enemy_ids:
        e = state.characters.get(eid)
        if e is None:
            continue
        enemies.append(
            CombatEnemy(
                name=e.name,
                hp=e.hp,
                hp_max=e.max_hp,
                alive=e.alive,
            )
        )

    return CombatBadgePayload(
        round=cs.round,
        turn_label=turn_label,
        enemies=enemies,
    )


def to_hero(state: GameState, graph: GameGraph | None = None) -> dict:
    """Dict adapter over `_build_hero_payload` for state-payload embedding."""
    if graph is None:
        graph = state.graph()
    return _build_hero_payload(state, graph).model_dump()


def to_subject(state: GameState, graph: GameGraph | None = None) -> dict | None:
    """Dict adapter over `_build_subject_payload` (None passes through)."""
    if graph is None:
        graph = state.graph()
    payload = _build_subject_payload(state, graph)
    return payload.model_dump() if payload else None


def to_quest(state: GameState, graph: GameGraph | None = None) -> dict | None:
    """Dict adapter over `_build_quest_payload` (None passes through)."""
    if graph is None:
        graph = state.graph()
    payload = _build_quest_payload(state, graph)
    return payload.model_dump() if payload else None


def to_place(state: GameState, graph: GameGraph | None = None) -> dict | None:
    """Dict adapter over `_build_place_payload` (None passes through)."""
    if graph is None:
        graph = state.graph()
    payload = _build_place_payload(state, graph)
    return payload.model_dump() if payload else None


def to_combat(state: GameState) -> dict | None:
    """Dict adapter over `_build_combat_badge_payload` (None passes through)."""
    payload = _build_combat_badge_payload(state)
    return payload.model_dump() if payload else None


def pending_check_to_front(state: GameState, pending: PendingCheck) -> dict:
    """`stat_label` is the Korean stat name (built here so the client doesn't
    re-derive it). `stat_value` is the player's current score on that stat.
    `reason` is shown verbatim above the dice strip."""
    from .emit import _build_pending_check_payload

    return _build_pending_check_payload(state, pending).model_dump()


def to_front_state(state: GameState, graph: GameGraph | None = None) -> dict:
    """Assemble the full client-side state payload. `graph` is the relational
    SSOT — flow finalize passes the turn-end graph; tests/api glue can omit
    and we'll build internally."""
    if graph is None:
        graph = state.graph()
    pending = state.pending_check
    return {
        "hero": to_hero(state, graph),
        "subject": to_subject(state, graph),
        "quest": to_quest(state, graph),
        "place": to_place(state, graph),
        "combat": to_combat(state),
        "log": [e.model_dump() for e in state.log_entries],
        "pendingCheck": pending_check_to_front(state, pending) if pending else None,
        "storyGraph": to_story_graph(state, graph),
    }
