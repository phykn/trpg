from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .verb import JudgeOutput, RefuseReason, Verb


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
    def _exactly_one(self) -> "ActionOutput":
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
        return self


def action_output_to_judge_output(
    output: ActionOutput,
    *,
    in_combat: bool = False,
) -> JudgeOutput:
    if output.refuse is not None:
        return JudgeOutput(refuse=output.refuse)
    verbs = [
        action_to_verb(action, in_combat=in_combat)
        for action in output.actions or []
    ]
    return JudgeOutput.model_validate(
        {"actions": [verb.model_dump(mode="json") for verb in verbs]},
        context={"in_combat": in_combat},
    )


def action_to_verb(action: Action, *, in_combat: bool = False) -> Verb:
    data: dict[str, Any]
    if action.verb == "move":
        modifiers: dict[str, Any] = {}
        destination = _single(action.to) or _single(action.what)
        if destination is not None:
            modifiers["destination"] = destination
        if action.how == "hasty" or (in_combat and action.how in (None, "flee")):
            modifiers["manner"] = "hasty"
        _copy_note(action, modifiers)
        data = {"name": "move", "modifiers": modifiers}
    elif action.verb == "transfer":
        modifiers = {
            "from_id": action.from_,
            "to_id": action.to,
            "mode": action.how or "gift",
        }
        item_id = _single(action.what) or _single(action.with_)
        if item_id is not None:
            modifiers["item_id"] = item_id
        _copy_note(action, modifiers)
        data = {"name": "transfer", "modifiers": _drop_none(modifiers)}
    elif action.verb == "use":
        modifiers = {"item_id": _single(action.what) or _single(action.with_)}
        if action.to is not None:
            modifiers["target_id"] = action.to
        _copy_note(action, modifiers)
        data = {"name": "use", "modifiers": _drop_none(modifiers)}
    elif action.verb == "attack":
        modifiers = {}
        if action.with_ is not None:
            modifiers["skill_id"] = action.with_
        if action.how == "surprise":
            modifiers["surprise"] = True
        _copy_note(action, modifiers)
        data = {
            "name": "attack",
            "target_ids": _list(action.what),
            "modifiers": modifiers,
        }
    elif action.verb == "cast":
        modifiers = {"skill_id": _single(action.with_) or _single(action.what)}
        _copy_note(action, modifiers)
        target_ids = _list(action.to)
        data = {
            "name": "cast",
            "target_ids": target_ids,
            "modifiers": _drop_none(modifiers),
        }
    elif action.verb == "speak":
        modifiers = {"intent": action.how or "friendly"}
        target_id = _single(action.to) or _single(action.what)
        if target_id is not None:
            modifiers["target"] = target_id
        _copy_note(action, modifiers)
        data = {"name": "speak", "modifiers": modifiers}
    elif action.verb == "perceive":
        data = {"name": "perceive", "target_ids": _list(action.what)}
    elif action.verb == "query":
        topic = _single(action.what)
        modifiers = {"topic": topic} if topic is not None else {}
        data = {"name": "query", "modifiers": modifiers}
    elif action.verb == "rest":
        data = {"name": "rest"}
    else:
        modifiers = {}
        _copy_note(action, modifiers)
        data = {"name": "wait", "modifiers": modifiers}
    return Verb.model_validate(data, context={"in_combat": in_combat})


def verb_to_action(verb: Verb) -> Action:
    modifiers = verb.modifiers or {}
    if verb.name == "move":
        return Action(
            verb="move",
            to=modifiers.get("destination"),
            how=modifiers.get("manner"),
            note=modifiers.get("tail_intent"),
        )
    if verb.name == "transfer":
        return Action(
            verb="transfer",
            what=modifiers.get("item_id"),
            from_=modifiers.get("from_id"),
            to=modifiers.get("to_id"),
            how=modifiers.get("mode"),
            note=modifiers.get("tail_intent"),
        )
    if verb.name == "use":
        return Action(
            verb="use",
            what=modifiers.get("item_id"),
            to=modifiers.get("target_id"),
            note=modifiers.get("tail_intent"),
        )
    if verb.name == "attack":
        return Action(
            verb="attack",
            what=list(verb.target_ids),
            with_=modifiers.get("skill_id"),
            how="surprise" if modifiers.get("surprise") else None,
            note=modifiers.get("tail_intent"),
        )
    if verb.name == "cast":
        return Action(
            verb="cast",
            what=list(verb.target_ids) or None,
            with_=modifiers.get("skill_id"),
            note=modifiers.get("tail_intent"),
        )
    if verb.name == "speak":
        return Action(
            verb="speak",
            what=modifiers.get("target"),
            how=modifiers.get("intent"),
            note=modifiers.get("tail_intent"),
        )
    if verb.name == "perceive":
        return Action(verb="perceive", what=list(verb.target_ids) or None)
    if verb.name == "query":
        return Action(verb="query", what=modifiers.get("topic"))
    if verb.name == "rest":
        return Action(verb="rest")
    return Action(verb="pass", note=modifiers.get("tail_intent"))


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


def _drop_none(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item is not None}


def _copy_note(action: Action, modifiers: dict[str, Any]) -> None:
    if action.note:
        modifiers["tail_intent"] = action.note
