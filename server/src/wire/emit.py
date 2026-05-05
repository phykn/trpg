import re
from typing import TYPE_CHECKING

from ..locale import render
from .models import (
    Equipment,
    EquipItem,
    ErrorPayload,
    HeroPayload,
    InventoryItem,
    PendingCheckPayload,
    StatEntry,
    TierBadge,
)

if TYPE_CHECKING:
    from ..domain.memory import PendingCheck
    from ..domain.state import GameState
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
    mapping.pending_check_to_front share one source of truth."""
    from ..domain.types import tier_to_int
    from ..mapping.labels import stat_label

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
    dict construction (mapping/to_front.to_hero delegates here). Pulls
    derivations from existing helpers — equipment/inventory/skills/companions
    via ontology queries, stats via stats_payload, level math via growth.
    Mirrors mapping/to_front._equipment / _inventory / _skill_names /
    _companion_label exactly so the JSON shape stays identical."""
    from collections import Counter

    from ..domain.entities import EQUIPMENT_SLOTS
    from ..engines.growth import can_afford_level_up, xp_for_next_level
    from ..mapping.labels import gender_label, race_job_label, stats_payload
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
