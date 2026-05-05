import re
from typing import TYPE_CHECKING, Literal

from ..locale import render
from .models import (
    CombatBadgePayload,
    CombatEndPayload,
    CombatEnemy,
    CombatStartPayload,
    CombatTurnPayload,
    DifficultyBadge,
    DonePayload,
    Equipment,
    EquipItem,
    ErrorPayload,
    HeroPayload,
    InventoryItem,
    JudgePayload,
    JudgePendingCheckTrigger,
    JudgeRefuse,
    JudgeVerb,
    JudgeVerbs,
    LogEntryPayload,
    NarrativeDeltaPayload,
    PendingCheckPayload,
    PlacePayload,
    PlaceSurrounding,
    PlaceTarget,
    QuestPayload,
    QuestRewards,
    RiskBadge,
    StatEntry,
    SubjectPayload,
    SuggestionsPayload,
    TierBadge,
)

if TYPE_CHECKING:
    from ..domain.memory import PendingCheck
    from ..domain.state import GameState
    from ..domain.types import StatKey, Tier
    from ..domain.verb import RefuseReason, Verb
    from ..ontology.graph import GameGraph

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _to_snake(name: str) -> str:
    return _CAMEL_BOUNDARY.sub("_", name).lower()


def emit_error(
    code_or_exc: str | Exception,
    *,
    locale: str = "ko",
    message: str | None = None,
    **vars: object,
) -> dict:
    """SSE error event.

    - `code_or_exc` is an Exception (uses class name as code) or a string code.
    - `message` overrides catalog lookup when provided.
    - `**vars` pass to render() for catalog template interpolation.
    - Catalog miss without explicit message falls back to error.runtime_generic.
    """
    if isinstance(code_or_exc, Exception):
        code = type(code_or_exc).__name__
    else:
        code = code_or_exc

    if message is None:
        key = f"error.{_to_snake(code)}"
        try:
            message = render(key, locale, **vars)
        except KeyError:
            message = render("error.runtime_generic", locale)

    payload = ErrorPayload(code=code, message=message)
    return {"type": "error", "data": payload.model_dump()}


def _build_pending_check_payload(
    state: "GameState", pending: "PendingCheck"
) -> PendingCheckPayload:
    """Build the wire model from domain state. Centralizes derivation
    (stat_label, stat_value, tier badge) so both emit_pending_check and
    wire.pending_check_to_front share one source of truth."""
    from ..domain.types import tier_to_int
    from .labels import stat_label

    actor = state.characters[state.player_id]
    return PendingCheckPayload(
        kind=pending.kind,
        dc=pending.dc,
        stat=pending.stat,
        stat_label=stat_label(pending.stat),
        stat_value=getattr(actor.stats, pending.stat),
        mod=pending.mod,
        required_roll=pending.required_roll,
        tier=TierBadge(
            value=tier_to_int(pending.tier),
            max=7,
            label=render(f"tier.{pending.tier}", "ko"),
        ),
        target=pending.target,
        reason=pending.reason,
    )


def emit_pending_check(state: "GameState", pending: "PendingCheck") -> dict:
    """SSE pending_check event. Mirrors emit_error pattern: state + pending →
    full {"type": "pending_check", "data": {...}} envelope."""
    payload = _build_pending_check_payload(state, pending)
    return {"type": "pending_check", "data": payload.model_dump()}


def _build_hero_payload(state: "GameState", graph: "GameGraph") -> HeroPayload:
    """Build the wire model for the `hero` state slot. SSOT for to_hero
    dict construction (wire/to_front.to_hero delegates here). Pulls
    derivations from existing helpers — equipment/inventory/skills/companions
    via ontology queries, stats via stats_payload, level math via growth.
    Mirrors wire/to_front._equipment / _inventory / _skill_names /
    _companion_label exactly so the JSON shape stays identical."""
    from collections import Counter

    from ..domain.entities import EQUIPMENT_SLOTS
    from ..engines.growth import can_afford_level_up, xp_for_next_level
    from .labels import gender_label, race_job_label, stats_payload
    from ..ontology.queries import (
        companions_of,
        equipment_of,
        inventory_of,
        known_skills_of,
    )
    from ..rules import RULES

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
        gender=gender_label(p),
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


def _build_subject_payload(
    state: "GameState", graph: "GameGraph"
) -> SubjectPayload | None:
    """Build the wire model for the `subject` state slot. Returns None when
    no subject is active or the active id no longer resolves — same gating
    as wire.to_subject. Mirrors wire.to_subject's exact derivation
    (known list = appearance + hints + player memories, equipment/inventory/
    skills via ontology queries, gold pseudo-row at inventory[0])."""
    from collections import Counter

    from ..domain.entities import EQUIPMENT_SLOTS
    from .labels import gender_label, race_job_label, stats_payload
    from ..ontology.queries import equipment_of, inventory_of, known_skills_of

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
        gender=gender_label(s),
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


def _build_quest_payload(
    state: "GameState", graph: "GameGraph"
) -> QuestPayload | None:
    """Build the wire model for the `quest` state slot. Returns None when
    no quest is active or the active id no longer resolves — same gating
    as wire.to_quest. Mirrors wire.to_quest's exact derivation
    (giver via giver_with_location_label, goals from triggers, progress
    label from triggers_met counts, action list from status)."""
    from .labels import difficulty_badge, giver_with_location_label

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
        conditions=list(q.conditions),
        rewards=QuestRewards(gold=q.rewards.gold, exp=q.rewards.exp),
        status=q.status,
        actions=actions,
    )


def _build_place_payload(
    state: "GameState", graph: "GameGraph"
) -> PlacePayload | None:
    """Build the wire model for the `place` state slot. Returns None when
    the player has no location or the id no longer resolves — same gating
    as wire.to_place. Mirrors wire.to_place's exact derivation
    (surroundings via connections_of, targets via inhabitants_of, blurb
    fallback chain, day_phase via clock + render, risk via risk_payload)."""
    from ..domain.clock import day_phase
    from ..locale import render
    from .labels import gender_label, race_job_label, risk_payload
    from ..ontology.queries import connections_of, inhabitants_of

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
                gender=gender_label(c),
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
        features=list(loc.tags),
        surroundings=surroundings,
        targets=targets,
        risk=RiskBadge(label=risk["label"], tone=risk["tone"]),
    )


def emit_judge_pending_check_trigger(
    *, tier: "Tier", stat: "StatKey", targets: list[str], reason: str
) -> dict:
    """SSE judge event — pending_check_trigger branch."""
    payload = JudgePayload(
        root=JudgePendingCheckTrigger(
            judge_kind="pending_check_trigger",
            tier=tier,
            stat=stat,
            targets=list(targets),
            reason=reason,
        )
    )
    return {"type": "judge", "data": payload.model_dump()}


def emit_judge_refuse(refuse: "RefuseReason") -> dict:
    """SSE judge event — refuse branch."""
    payload = JudgePayload(
        root=JudgeRefuse(judge_kind="refuse", refuse=refuse)
    )
    return {"type": "judge", "data": payload.model_dump()}


def emit_judge_verb(verb: "Verb") -> dict:
    """SSE judge event — single-verb branch."""
    payload = JudgePayload(
        root=JudgeVerb(judge_kind="verb", verb=verb)
    )
    return {"type": "judge", "data": payload.model_dump()}


def emit_judge_verbs(actions: list["Verb"]) -> dict:
    """SSE judge event — multi-verb chain branch."""
    payload = JudgePayload(
        root=JudgeVerbs(judge_kind="verbs", actions=list(actions))
    )
    return {"type": "judge", "data": payload.model_dump()}


def emit_log_entry(log) -> dict:
    """SSE log_entry event. Wraps a GMLogEntry / PlayerLogEntry /
    ActLogEntry / RollLogEntry instance. Caller passes the already-built
    domain log object; the discriminated-union validator rejects anything
    else with ValidationError (loud-fail consistent with other builders)."""
    payload = LogEntryPayload(root=log)
    return {"type": "log_entry", "data": payload.model_dump()}


def emit_narrative_delta(text: str) -> dict:
    """SSE narrative_delta event. Streams a prose chunk to the client."""
    payload = NarrativeDeltaPayload(text=text)
    return {"type": "narrative_delta", "data": payload.model_dump()}


def emit_suggestions(items: list[str]) -> dict:
    """SSE suggestions event. Defensive list copy."""
    payload = SuggestionsPayload(items=list(items))
    return {"type": "suggestions", "data": payload.model_dump()}


def emit_done() -> dict:
    """SSE done event. Empty payload — turn-end marker."""
    payload = DonePayload()
    return {"type": "done", "data": payload.model_dump()}


def emit_combat_start(
    *,
    turn_order: list[str],
    round: int,
    surprise: Literal["player", "enemy"] | None,
    enemy_ids: list[str],
) -> dict:
    """SSE combat_start event. Defensive list copies for turn_order/enemy_ids."""
    payload = CombatStartPayload(
        turn_order=list(turn_order),
        round=round,
        surprise=surprise,
        enemy_ids=list(enemy_ids),
    )
    return {"type": "combat_start", "data": payload.model_dump()}


def emit_combat_turn(payload: "CombatTurnPayload | dict") -> dict:
    """SSE combat_turn event. Accepts either a CombatTurnPayload instance or
    a raw dict (auto-combat emits dicts via _turn_event factory). Dict input
    is validated against CombatTurnPayload — loud-fail on shape mismatch."""
    if not isinstance(payload, CombatTurnPayload):
        payload = CombatTurnPayload.model_validate(payload)
    return {"type": "combat_turn", "data": payload.model_dump()}


def emit_combat_end(
    outcome: Literal["victory", "defeat", "downed", "fled"],
) -> dict:
    """SSE combat_end event."""
    payload = CombatEndPayload(outcome=outcome)
    return {"type": "combat_end", "data": payload.model_dump()}


def _build_combat_badge_payload(state: "GameState") -> CombatBadgePayload | None:
    """Build the wire model for the `combat` state slot. Returns None when
    there's no active combat or turn_order is empty — same gating as
    wire.to_combat. Mirrors wire.to_combat's exact derivation
    (current actor lookup, "내 차례" vs "{name} 차례" composition,
    enemy filtering by character existence)."""
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
        enemies.append(CombatEnemy(
            name=e.name, hp=e.hp, hp_max=e.max_hp, alive=e.alive,
        ))

    return CombatBadgePayload(
        round=cs.round,
        turn_label=turn_label,
        enemies=enemies,
    )
