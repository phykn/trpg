from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from ..domain.types import Grade, Intent
from ..rules import RULES
from ..state.models import GameState


# --- state_change 스키마 -----------------------------------------------------


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


# --- set 권한 매트릭스 -------------------------------------------------------

_CHAR_FORBIDDEN = frozenset({
    "relations", "inventory_ids", "memories", "racial_skills",
    "learned_skills", "companions", "active_buffs", "hints",
    "hp", "max_hp", "mp", "max_mp", "xp_pool", "gold",
    "alive", "in_combat", "death_saves", "revive_coins", "level",
    "id", "is_player", "race_id",
})

_ITEM_FORBIDDEN = frozenset({"id", "effects", "required"})

_LOC_FORBIDDEN = frozenset({
    "id", "item_ids", "hidden_items", "hidden_connections",
    "connections", "sleep_encounters",
})

_CHAPTER_QUEST_ALLOWED = frozenset({"summary", "status"})


def _check_set_permission(entity: str, field: str) -> str | None:
    top = field.split(".", 1)[0]
    if entity in ("chapters", "quests"):
        if top not in _CHAPTER_QUEST_ALLOWED:
            return f"narrator can only set 'summary' or 'status' on {entity}"
        return None
    forbidden_map = {
        "characters": _CHAR_FORBIDDEN,
        "items": _ITEM_FORBIDDEN,
        "locations": _LOC_FORBIDDEN,
    }
    forbidden = forbidden_map[entity]
    if top in forbidden:
        return f"field {field!r} on {entity!r} is engine-owned"
    return None


# --- 핸들러 5종 --------------------------------------------------------------


class _StateChangeError(ValueError):
    pass


def _set_dotted(obj: Any, dotted_field: str, value: Any) -> None:
    parts = dotted_field.split(".")
    for part in parts[:-1]:
        obj = getattr(obj, part)
    setattr(obj, parts[-1], value)


def _apply_set(state: GameState, c: SetChange) -> None:
    reason = _check_set_permission(c.entity, c.field)
    if reason:
        raise _StateChangeError(reason)
    container = getattr(state, c.entity)
    if c.id not in container:
        raise _StateChangeError(f"unknown {c.entity} id: {c.id!r}")
    try:
        _set_dotted(container[c.id], c.field, c.value)
    except (AttributeError, ValidationError) as e:
        raise _StateChangeError(f"failed to set {c.field!r}: {e}") from e


def _apply_set_time(state: GameState, c: SetTimeChange) -> None:
    if c.value < state.world_time:
        raise _StateChangeError(
            f"set_time {c.value!r} < current {state.world_time!r} (시간 역행 금지)"
        )
    state.world_time = c.value


def _apply_move(state: GameState, c: MoveChange) -> None:
    if c.target not in state.characters:
        raise _StateChangeError(f"unknown character: {c.target!r}")
    if c.destination not in state.locations:
        raise _StateChangeError(f"unknown location: {c.destination!r}")
    state.characters[c.target].location_id = c.destination


def _resolve_inventory(state: GameState, container_id: str) -> list[str]:
    if container_id in state.characters:
        return state.characters[container_id].inventory_ids
    if container_id in state.locations:
        return state.locations[container_id].item_ids
    raise _StateChangeError(f"unknown container: {container_id!r}")


def _apply_move_item(state: GameState, c: MoveItemChange) -> None:
    if c.item not in state.items:
        raise _StateChangeError(f"unknown item: {c.item!r}")
    src = _resolve_inventory(state, c.from_)
    dst = _resolve_inventory(state, c.to)
    if c.item not in src:
        raise _StateChangeError(f"item {c.item!r} not in {c.from_!r}")
    src.remove(c.item)
    dst.append(c.item)


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


def _apply_affinity(state: GameState, c: AffinityChange) -> None:
    if c.actor not in state.characters:
        raise _StateChangeError(f"unknown actor: {c.actor!r}")
    actor = state.characters[c.actor]
    delta = _affinity_delta(c.grade, c.intent)
    current = actor.relations.get(c.target, 0)
    actor.relations[c.target] = max(-100, min(100, current + delta))


_HANDLERS = {
    "set": _apply_set,
    "set_time": _apply_set_time,
    "move": _apply_move,
    "move_item": _apply_move_item,
    "affinity": _apply_affinity,
}


# --- 엔트리 -----------------------------------------------------------------


def _format_validation_error(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"]) or "<root>"
        parts.append(f"{loc}: {err['msg']}")
    return "; ".join(parts)


def apply_changes(state: GameState, raw_changes: list[dict]) -> dict:
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
            _HANDLERS[change.type](state, change)
            applied += 1
        except _StateChangeError as e:
            rejected.append({"index": idx, "change": raw, "reason": str(e)})
    return {"applied": applied, "rejected": rejected, "world_time": state.world_time}
