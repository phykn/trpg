"""state_changes — five mutation kinds (set, set_time, move, move_item,
affinity) the LLM emits as part of NarrateOutput. Each kind has its own
permission matrix; forbidden fields drop silently per change, the rest of
the batch still applies. Time may not run backwards."""
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from ..domain.types import Grade, Intent
from ..rules import RULES
from ..domain.state import GameState


# --- change models ---------------------------------------------------------


class SetChange(BaseModel):
    type: Literal["set"]
    entity: Literal["characters", "items", "locations", "chapters", "quests"]
    id: str
    field: str
    value: Any = None


class SetTimeChange(BaseModel):
    type: Literal["set_time"]
    value: str  # ISO 8601


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
    SetChange | SetTimeChange | MoveChange | MoveItemChange | AffinityChange,
    Field(discriminator="type"),
]

_state_change_adapter = TypeAdapter(StateChange)


# --- permission matrix -----------------------------------------------------


_CHAR_FORBIDDEN = frozenset(
    {
        "relations",
        "inventory_ids",
        "memories",
        "racial_skill_ids",
        "learned_skill_ids",
        "companions",
        "active_buffs",
        "hints",
        "hp",
        "max_hp",
        "mp",
        "max_mp",
        "xp_pool",
        "xp_reward",
        "gold",
        "alive",
        "death_saves",
        "revive_coins",
        "level",
        "id",
        "is_player",
        "race_id",
    }
)

_ITEM_FORBIDDEN = frozenset({"id", "effects", "required"})

_LOC_FORBIDDEN = frozenset(
    {
        "id",
        "item_ids",
        "hidden_items",
        "hidden_connections",
        "connections",
        "sleep_encounters",
    }
)

_CHAPTER_QUEST_ALLOWED = frozenset({"summary", "status"})

_FORBIDDEN_BY_ENTITY: dict[str, frozenset[str]] = {
    "characters": _CHAR_FORBIDDEN,
    "items": _ITEM_FORBIDDEN,
    "locations": _LOC_FORBIDDEN,
}


def _check_set_permission(entity: str, field: str) -> str | None:
    top = field.split(".", 1)[0]
    if entity in ("chapters", "quests"):
        if top not in _CHAPTER_QUEST_ALLOWED:
            return f"narrator can only set 'summary' or 'status' on {entity}"
        return None
    if top in _FORBIDDEN_BY_ENTITY[entity]:
        return f"field {field!r} on {entity!r} is engine-owned"
    return None


class _StateChangeError(ValueError):
    pass


# --- per-kind handlers -----------------------------------------------------


def _set_dotted(obj: Any, dotted_field: str, value: Any) -> None:
    parts = dotted_field.split(".")
    for part in parts[:-1]:
        obj = getattr(obj, part)
    field_name = parts[-1]
    fields = getattr(type(obj), "model_fields", None)
    if fields is None or field_name not in fields:
        raise AttributeError(
            f"{type(obj).__name__!r} has no field {field_name!r}"
        )
    # Pydantic's default setattr skips type validation, so a bad value
    # (e.g. a str where a list[str] is expected, or None on a non-nullable
    # field) survives until the next read and surfaces as PersistenceFailed.
    # Validate against the declared annotation up front so apply_changes can
    # reject the change cleanly instead.
    coerced = TypeAdapter(fields[field_name].annotation).validate_python(value)
    setattr(obj, field_name, coerced)


def _apply_set(
    state: GameState,
    c: SetChange,
    dirty: set[tuple[str, str]] | None,
) -> None:
    reason = _check_set_permission(c.entity, c.field)
    if reason:
        raise _StateChangeError(reason)
    container = getattr(state, c.entity)
    if c.id not in container:
        raise _StateChangeError(f"unknown {c.entity} id: {c.id!r}")
    try:
        _set_dotted(container[c.id], c.field, c.value)
    except (AttributeError, ValueError, ValidationError) as e:
        # Pydantic v2 raises ValueError ("object has no field 'X'") for unknown
        # fields under `extra='ignore'`. AttributeError covers nested .getattr
        # failures, ValidationError covers type/range mismatches.
        raise _StateChangeError(f"failed to set {c.field!r}: {e}") from e
    if dirty is not None:
        dirty.add((c.entity, c.id))


def _apply_set_time(
    state: GameState,
    c: SetTimeChange,
    dirty: set[tuple[str, str]] | None,
) -> None:
    if c.value < state.world_time:
        raise _StateChangeError(
            f"set_time {c.value!r} < current {state.world_time!r} (no time travel)"
        )
    state.world_time = c.value


def _apply_move(
    state: GameState,
    c: MoveChange,
    dirty: set[tuple[str, str]] | None,
) -> None:
    from .quest import check_quests  # deferred import — keeps the cross-layer boundary clean

    if c.target not in state.characters:
        raise _StateChangeError(f"unknown character: {c.target!r}")
    if c.destination not in state.locations:
        raise _StateChangeError(f"unknown location: {c.destination!r}")
    state.characters[c.target].location_id = c.destination
    if dirty is not None:
        dirty.add(("characters", c.target))
    # Companions (P3 §2.9) — move with the patron.
    for cid in state.characters[c.target].companions:
        if cid in state.characters:
            state.characters[cid].location_id = c.destination
            if dirty is not None:
                dirty.add(("characters", cid))
    # quest hook — only the player move is evaluated (NPC moves are not quest triggers).
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
    dirty: set[tuple[str, str]] | None,
) -> None:
    if c.item not in state.items:
        raise _StateChangeError(f"unknown item: {c.item!r}")
    src_kind, src = _resolve_inventory(state, c.from_)
    dst_kind, dst = _resolve_inventory(state, c.to)
    if c.item not in src:
        raise _StateChangeError(f"item {c.item!r} not in {c.from_!r}")
    src.remove(c.item)
    dst.append(c.item)
    if dirty is not None:
        dirty.add((src_kind, c.from_))
        dirty.add((dst_kind, c.to))


def _affinity_delta(grade: Grade, intent: Intent) -> int:
    base = {
        "critical_success": RULES.social.affinity_critical,
        "success": RULES.social.affinity_success,
        "partial_success": RULES.social.affinity_success,
        "failure": RULES.social.affinity_failure,
        "critical_failure": -RULES.social.affinity_critical,
    }[grade]
    if intent == "hostile":
        return -base
    if intent == "deceptive":
        if grade in ("critical_success", "success", "partial_success"):
            return 0
        return base * 2
    return base


def _apply_affinity(
    state: GameState,
    c: AffinityChange,
    dirty: set[tuple[str, str]] | None,
) -> None:
    if c.actor not in state.characters:
        raise _StateChangeError(f"unknown actor: {c.actor!r}")
    actor = state.characters[c.actor]
    delta = _affinity_delta(c.grade, c.intent)
    current = actor.relations.get(c.target, 0)
    actor.relations[c.target] = max(-100, min(100, current + delta))
    if dirty is not None:
        dirty.add(("characters", c.actor))


# --- public dispatch -------------------------------------------------------


_HANDLERS = {
    "set": _apply_set,
    "set_time": _apply_set_time,
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
    dirty: set[tuple[str, str]] | None = None,
) -> dict:
    """Apply state_changes to `state`. If `dirty` is provided, populate it
    with `(entity_kind, entity_id)` tuples for every change that successfully
    mutates an entity file. `set_time` only touches meta, not entities."""
    applied = 0
    rejected: list[dict] = []
    for idx, raw in enumerate(raw_changes):
        try:
            change = _state_change_adapter.validate_python(raw)
        except ValidationError as e:
            rejected.append(
                {"index": idx, "change": raw, "reason": _format_validation_error(e)}
            )
            continue
        try:
            _HANDLERS[change.type](state, change, dirty)
            applied += 1
        except _StateChangeError as e:
            rejected.append({"index": idx, "change": raw, "reason": str(e)})
    return {"applied": applied, "rejected": rejected, "world_time": state.world_time}
