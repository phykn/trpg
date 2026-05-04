from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from ..domain.entities import EQUIPMENT_SLOTS
from ..domain.types import Grade, Intent
from ..rules import RULES
from ..rules.permissions import CHAPTER_QUEST_ALLOWED, FORBIDDEN_BY_ENTITY
from ..domain.state import GameState


class SetChange(BaseModel):
    type: Literal["set"]
    entity: Literal["characters", "items", "locations", "chapters", "quests"]
    id: str
    field: str
    value: Any = None


class MoveChange(BaseModel):
    type: Literal["move"]
    target: str
    destination: str


class MoveItemChange(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    type: Literal["move_item"]
    item: str
    from_: str = Field(alias="from")
    to: str


class AffinityChange(BaseModel):
    type: Literal["affinity"]
    actor: str
    target: str
    grade: Grade
    intent: Intent = "friendly"


StateChange = Annotated[
    SetChange | MoveChange | MoveItemChange | AffinityChange,
    Field(discriminator="type"),
]

_state_change_adapter = TypeAdapter(StateChange)


def _check_set_permission(entity: str, field: str) -> str | None:
    top = field.split(".", 1)[0]
    if entity in ("chapters", "quests"):
        if top not in CHAPTER_QUEST_ALLOWED:
            return f"narrator can only set 'summary' or 'status' on {entity}"
        return None
    if top in FORBIDDEN_BY_ENTITY[entity]:
        return f"field {field!r} on {entity!r} is engine-owned"
    return None


class _StateChangeError(ValueError):
    pass


def _set_dotted(obj: Any, dotted_field: str, value: Any) -> None:
    parts = dotted_field.split(".")
    for part in parts[:-1]:
        obj = getattr(obj, part)
    field_name = parts[-1]
    fields = getattr(type(obj), "model_fields", None)
    if fields is None or field_name not in fields:
        raise AttributeError(f"{type(obj).__name__!r} has no field {field_name!r}")
    # Validate against the annotation up front; Pydantic's setattr skips type checks and a bad value would only surface later as PersistenceFailed.
    coerced = TypeAdapter(fields[field_name].annotation).validate_python(value)
    setattr(obj, field_name, coerced)


def _apply_set(
    state: GameState,
    c: SetChange,
    dirty,
) -> None:
    from .quest import _entities_set

    entities = _entities_set(dirty)
    reason = _check_set_permission(c.entity, c.field)
    if reason:
        raise _StateChangeError(reason)
    container = getattr(state, c.entity)
    if c.id not in container:
        raise _StateChangeError(f"unknown {c.entity} id: {c.id!r}")
    try:
        _set_dotted(container[c.id], c.field, c.value)
    except (AttributeError, ValueError, ValidationError) as e:
        raise _StateChangeError(f"failed to set {c.field!r}: {e}") from e
    if entities is not None:
        entities.add((c.entity, c.id))
    # Narrate's locked → active flip would otherwise leave active_quest_id pointing at the previous quest.
    if c.entity == "quests" and c.field == "status":
        from .quest import _refresh_active_quest_id

        _refresh_active_quest_id(state)


def _apply_move(
    state: GameState,
    c: MoveChange,
    dirty,
) -> None:
    from .quest import (
        _entities_set,
        check_quests,
    )  # deferred import keeps the cross-layer boundary clean
    from ..ontology.queries import connections_of

    entities = _entities_set(dirty)

    if c.target not in state.characters:
        raise _StateChangeError(f"unknown character: {c.target!r}")
    if c.destination not in state.locations:
        raise _StateChangeError(f"unknown location: {c.destination!r}")
    # Only the player's move is gated; NPC moves are trusted (quest hooks / companion follow).
    if c.target == state.player_id:
        current_loc_id = state.characters[c.target].location_id
        if current_loc_id is not None and c.destination != current_loc_id:
            graph = state.graph()
            reachable = {edge.to_id for edge in connections_of(graph, current_loc_id)}
            if c.destination not in reachable:
                raise _StateChangeError(
                    f"destination {c.destination!r} is not adjacent to current "
                    f"location {current_loc_id!r}. Reachable: {sorted(reachable)}."
                )
    state.characters[c.target].location_id = c.destination
    # "Moving to a location implies visiting it" — engine-level invariant so
    # callers in flow/ don't each have to remember to update visited_location_ids.
    state.characters[c.target].visited_location_ids.add(c.destination)
    if entities is not None:
        entities.add(("characters", c.target))
    # Companions move with the patron.
    for cid in state.characters[c.target].companions:
        if cid in state.characters:
            state.characters[cid].location_id = c.destination
            state.characters[cid].visited_location_ids.add(c.destination)
            if entities is not None:
                entities.add(("characters", cid))
    if c.target == state.player_id:
        check_quests(state, "location_enter", c.destination, dirty)


def _resolve_inventory(state: GameState, container_id: str) -> tuple[str, list[str]]:
    """Return (kind, inventory list) for a container id."""
    if container_id in state.characters:
        return "characters", state.characters[container_id].inventory_ids
    if container_id in state.locations:
        return "locations", state.locations[container_id].item_ids
    raise _StateChangeError(f"unknown container: {container_id!r}")


def _apply_move_item(
    state: GameState,
    c: MoveItemChange,
    dirty,
) -> None:
    from .quest import _entities_set

    entities = _entities_set(dirty)
    if c.item not in state.items:
        raise _StateChangeError(f"unknown item: {c.item!r}")
    src_kind, src = _resolve_inventory(state, c.from_)
    dst_kind, dst = _resolve_inventory(state, c.to)
    if c.item not in src:
        raise _StateChangeError(f"item {c.item!r} not in {c.from_!r}")
    src.remove(c.item)
    dst.append(c.item)
    if src_kind == "characters":
        equipment = state.characters[c.from_].equipment
        for slot in EQUIPMENT_SLOTS:
            if getattr(equipment, slot) == c.item:
                setattr(equipment, slot, None)
    if entities is not None:
        entities.add((src_kind, c.from_))
        entities.add((dst_kind, c.to))


def _affinity_delta(grade: Grade, intent: Intent) -> int:
    base = {
        "critical_success": RULES.social.affinity_critical,
        "success": RULES.social.affinity_success,
        "partial_success": RULES.social.affinity_success,
        "failure": RULES.social.affinity_failure,
        "critical_failure": -RULES.social.affinity_critical,
    }[grade]
    if intent == "hostile":
        # Cap at 0: a botched threat shouldn't *endear* the actor to the target.
        # Without this, hostile + critical_failure flipped to +10 (same as a successful befriend).
        return min(0, -base)
    if intent == "deceptive":
        if grade in ("critical_success", "success", "partial_success"):
            return 0
        return base * 2
    return base


def _apply_affinity(
    state: GameState,
    c: AffinityChange,
    dirty,
) -> None:
    """Single-direction write: only `target.relations[actor]`. Reverse direction is unused by gameplay."""
    from .quest import _entities_set

    entities = _entities_set(dirty)
    if c.actor not in state.characters:
        raise _StateChangeError(f"unknown actor: {c.actor!r}")
    if c.target not in state.characters:
        raise _StateChangeError(f"unknown target: {c.target!r}")
    target = state.characters[c.target]
    delta = _affinity_delta(c.grade, c.intent)
    current = target.relations.get(c.actor, 0)
    target.relations[c.actor] = max(-100, min(100, current + delta))
    if entities is not None:
        entities.add(("characters", c.target))


def apply_combat_affinity_drop(
    state: GameState,
    attacker_id: str,
    target_id: str,
    dirty=None,
) -> None:
    """Combat-side affinity drop. Single direction (`target.relations[attacker]`); narrate's affinity change never fires here.
    With a full `Dirty`, also queues a deferred reaction card so the player
    sees the hostility shift after the combat result."""
    from .quest import _as_dirty, _entities_set

    entities = _entities_set(dirty)
    full = _as_dirty(dirty)
    if attacker_id == target_id:
        return
    target = state.characters.get(target_id)
    if target is None:
        return
    delta = RULES.social.combat_affinity_drop
    current = target.relations.get(attacker_id, 0)
    new_val = max(-100, min(100, current - delta))
    actual_delta = new_val - current
    target.relations[attacker_id] = new_val
    if entities is not None:
        entities.add(("characters", target_id))
    if full is not None and actual_delta != 0 and state.combat_state is None:
        from ..flow.format import format_affinity_card_log, format_affinity_card_turn_log

        full.deferred_act_cards.append(
            (
                format_affinity_card_log(target.name, actual_delta),
                format_affinity_card_turn_log(target.name, actual_delta),
            )
        )


_HANDLERS = {
    "set": _apply_set,
    "move": _apply_move,
    "move_item": _apply_move_item,
    "affinity": _apply_affinity,
}


def _format_validation_error(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "<root>"
        parts.append(f"{loc}: {err['msg']}")
    return "; ".join(parts)


def apply_changes(
    state: GameState,
    raw_changes: list[dict],
    dirty=None,
) -> dict:
    """Apply state_changes to `state`. `dirty` accepts the legacy entity-set
    or a full `Dirty`; downstream check_quests uses the full form to push the
    quest success card on completion. Either way, the entity set is grown.

    Returns:
      - "applied": int — count of successfully applied changes
      - "rejected": list[dict] — per-change failure records
      - "started_quests": list[str] — quest ids that flipped locked → active
      - "affinity_deltas": list[tuple[str, int]] — (target_id, signed delta) per applied affinity change
      - "exp_deltas": list[int] — reserved; engine xp paths bypass apply_changes and xp_pool is engine-owned, so always empty
    """
    applied = 0
    rejected: list[dict] = []
    started_quests: list[str] = []
    affinity_deltas: list[tuple[str, int]] = []
    exp_deltas: list[int] = []
    for idx, raw in enumerate(raw_changes):
        try:
            change = _state_change_adapter.validate_python(raw)
        except ValidationError as e:
            rejected.append(
                {"index": idx, "change": raw, "reason": _format_validation_error(e)}
            )
            continue
        # Snapshot quest status pre-apply so locked → active flip is detectable.
        is_quest_status_set = (
            isinstance(change, SetChange)
            and change.entity == "quests"
            and change.field == "status"
            and change.value == "active"
        )
        prev_status: str | None = None
        if is_quest_status_set:
            quest = state.quests.get(change.id)
            prev_status = quest.status if quest is not None else None
        # Snapshot affinity pre-apply so the engine-computed signed delta is recoverable.
        is_affinity = isinstance(change, AffinityChange)
        prev_affinity: int | None = None
        if is_affinity:
            tgt = state.characters.get(change.target)
            prev_affinity = (
                tgt.relations.get(change.actor, 0) if tgt is not None else None
            )
        try:
            _HANDLERS[change.type](state, change, dirty)
            applied += 1
            if (
                is_quest_status_set
                and prev_status is not None
                and prev_status != "active"
            ):
                started_quests.append(change.id)
            if is_affinity and prev_affinity is not None:
                tgt = state.characters.get(change.target)
                if tgt is not None:
                    delta = tgt.relations.get(change.actor, 0) - prev_affinity
                    if delta != 0:
                        affinity_deltas.append((change.target, delta))
        except _StateChangeError as e:
            rejected.append({"index": idx, "change": raw, "reason": str(e)})
    return {
        "applied": applied,
        "rejected": rejected,
        "started_quests": started_quests,
        "affinity_deltas": affinity_deltas,
        "exp_deltas": exp_deltas,
    }
