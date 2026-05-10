from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, model_validator


ActionVerb = Literal[
    "move",
    "transfer",
    "use",
    "attack",
    "cast",
    "speak",
    "perceive",
    "query",
    "rest",
    "pass",
]

ActionValue = str | list[str]
RefuseCategory = Literal["out_of_game", "meta_breaking"]

_TRANSFER_HOW = {"gift", "trade", "steal", "accept", "abandon", "equip", "unequip"}
_SPEAK_HOW = {"friendly", "hostile", "deceptive", "recruit", "part", "accept", "abandon"}
_QUERY_TOPICS = {"surroundings", "exits", "inventory", "quests", "status"}


class RefuseReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: RefuseCategory
    message_hint: str = Field(min_length=1, max_length=120)


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    verb: ActionVerb
    what: ActionValue | None = None
    from_: str | None = Field(default=None, alias="from")
    to: str | None = None
    with_: str | None = Field(default=None, alias="with")
    how: str | None = None
    note: str | None = None


class ActionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actions: list[Action] | None = Field(default=None, max_length=4)
    refuse: RefuseReason | None = None

    @model_validator(mode="after")
    def _check_contract(self, info: ValidationInfo) -> "ActionOutput":
        actions_set = self.actions is not None
        refuse_set = self.refuse is not None
        if actions_set == refuse_set:
            raise ValueError(
                f"ActionOutput must set exactly one of {{actions, refuse}}; "
                f"got actions={actions_set}, refuse={refuse_set}"
            )
        if actions_set and len(self.actions) == 0:
            raise ValueError(
                "actions, if set, must contain >=1 action (use 'pass' for no-op)"
            )
        if actions_set and any(action.verb == "query" for action in self.actions):
            if len(self.actions) != 1:
                raise ValueError("query must be the only action")
        if actions_set:
            in_combat = bool((info.context or {}).get("in_combat", False))
            for action in self.actions:
                _validate_classifier_action(action, in_combat=in_combat)
        return self


def _validate_classifier_action(action: Action, *, in_combat: bool) -> None:
    if action.verb == "move":
        destination = _single(action.to) or _single(action.what)
        if destination is None and not in_combat:
            raise ValueError("action=move requires to or what outside combat")
        _require_enum(action.how, {"hasty", "flee"}, "move.how", optional=True)
        return

    if action.verb == "transfer":
        _require_string(action.from_, "transfer.from")
        _require_string(action.to, "transfer.to")
        _require_enum(action.how, _TRANSFER_HOW, "transfer.how")
        return

    if action.verb == "use":
        _require_string(_single(action.what) or _single(action.with_), "use.what")
        return

    if action.verb == "attack":
        _require_targets(action.what, "attack.what", required=True)
        _require_enum(action.how, {"surprise"}, "attack.how", optional=True)
        return

    if action.verb == "cast":
        _require_string(_single(action.with_) or _single(action.what), "cast.with")
        _require_targets(action.to, "cast.to", required=False)
        return

    if action.verb == "speak":
        _require_enum(action.how, _SPEAK_HOW, "speak.how")
        return

    if action.verb == "perceive":
        _require_targets(action.what, "perceive.what", required=False)
        return

    if action.verb == "query":
        topic = _single(action.what)
        if topic is not None:
            _require_enum(topic, _QUERY_TOPICS, "query.what")


def _single(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value and isinstance(value[0], str):
        return value[0]
    return None


def _list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _require_string(value: object, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} is required")


def _require_enum(
    value: object,
    allowed: set[str],
    field: str,
    *,
    optional: bool = False,
) -> None:
    if value is None and optional:
        return
    if value not in allowed:
        raise ValueError(f"{field} must be one of {sorted(allowed)}")


def _require_targets(value: object, field: str, *, required: bool) -> None:
    targets = _list(value)
    if required and not targets:
        raise ValueError(f"{field} requires at least one target id")
    if len(targets) > 8:
        raise ValueError(f"{field} allows at most 8 target ids")
