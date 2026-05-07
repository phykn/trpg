"""Verb-grammar primitives.

Lives in `game/domain/` so `game.domain.memory.PendingCheck` can carry `Verb` directly
without depending on `llm/calls/classify` (cycle through wire/labels →
game/domain/entities → game/domain/memory). `llm/calls/classify/schema.py` re-exports
these for call-site convenience.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, model_validator

VerbName = Literal[
    "move",
    "transfer",
    "use",
    "attack",
    "cast",
    "speak",
    "perceive",
    "rest",
    "wait",
]
RefuseCategory = Literal["out_of_game", "meta_breaking"]
TargetCardinality = Literal["forbidden", "optional", "required_one", "required_many"]


@dataclass(frozen=True)
class _ModifierSchema:
    required_modifiers: frozenset[str] = frozenset()
    optional_modifiers: dict[str, type | tuple[Any, ...]] = field(default_factory=dict)
    target_cardinality: TargetCardinality = "forbidden"


_MODIFIER_SCHEMAS: dict[VerbName, _ModifierSchema] = {
    "move": _ModifierSchema(
        required_modifiers=frozenset({"destination"}),
        optional_modifiers={
            "destination": str,
            "manner": ("hasty",),
            "tail_intent": str,
        },
        target_cardinality="forbidden",
    ),
    "transfer": _ModifierSchema(
        required_modifiers=frozenset({"from_id", "to_id", "mode"}),
        optional_modifiers={
            "from_id": str,
            "to_id": str,
            "mode": ("gift", "trade", "steal"),
            "item_id": str,
            "price": int,
            "tail_intent": str,
        },
        target_cardinality="forbidden",
    ),
    "use": _ModifierSchema(
        required_modifiers=frozenset({"item_id"}),
        optional_modifiers={"item_id": str, "target_id": str, "tail_intent": str},
        target_cardinality="forbidden",
    ),
    "attack": _ModifierSchema(
        required_modifiers=frozenset(),
        optional_modifiers={
            "surprise": bool,
            "skill_id": str,
            "tail_intent": str,
        },
        target_cardinality="required_many",
    ),
    "cast": _ModifierSchema(
        required_modifiers=frozenset({"skill_id"}),
        optional_modifiers={"skill_id": str, "tail_intent": str},
        target_cardinality="optional",
    ),
    "speak": _ModifierSchema(
        required_modifiers=frozenset({"intent"}),
        optional_modifiers={
            "intent": ("friendly", "hostile", "deceptive", "recruit", "part", "accept"),
            "target": str,
            "tail_intent": str,
        },
        target_cardinality="forbidden",
    ),
    "perceive": _ModifierSchema(
        required_modifiers=frozenset(),
        optional_modifiers={},
        target_cardinality="optional",
    ),
    "rest": _ModifierSchema(
        required_modifiers=frozenset(),
        optional_modifiers={},
        target_cardinality="forbidden",
    ),
    "wait": _ModifierSchema(
        required_modifiers=frozenset(),
        optional_modifiers={
            "tail_intent": str,
        },
        target_cardinality="forbidden",
    ),
}


class Verb(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: VerbName
    target_ids: list[str] = Field(default_factory=list, max_length=8)
    modifiers: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_modifiers(self, info: ValidationInfo) -> "Verb":
        # Save/load round-trip: skip the modifier-rule check. Saved verbs already
        # passed once at classify time and we don't have in_combat context here.
        if info.context is None:
            return self
        in_combat = bool(info.context.get("in_combat", False))
        schema = _MODIFIER_SCHEMAS[self.name]

        allowed = schema.required_modifiers | set(schema.optional_modifiers.keys())
        for k in [k for k in self.modifiers if k not in allowed]:
            self.modifiers.pop(k)

        missing = schema.required_modifiers - set(self.modifiers.keys())
        if self.name == "move" and in_combat:
            missing -= {"destination"}
        if missing:
            raise ValueError(
                f"verb={self.name} missing required modifiers: {sorted(missing)}"
            )

        for k, v in self.modifiers.items():
            spec = schema.optional_modifiers.get(k)
            if spec is None and k in schema.required_modifiers:
                spec = str
            if spec is None:
                continue
            if isinstance(spec, tuple):
                if v not in spec:
                    raise ValueError(
                        f"verb={self.name}.modifiers[{k}]={v!r} not in {spec}"
                    )
            elif isinstance(spec, type):
                if not isinstance(v, spec):
                    raise ValueError(
                        f"verb={self.name}.modifiers[{k}]={v!r} not {spec.__name__}"
                    )

        n = len(self.target_ids)
        cardinality = schema.target_cardinality
        if cardinality == "forbidden" and n > 0:
            raise ValueError(f"verb={self.name} forbids target_ids; got {n}")
        if cardinality == "required_one" and n != 1:
            raise ValueError(
                f"verb={self.name} requires exactly 1 target_id; got {n}"
            )
        if cardinality == "required_many" and n < 1:
            raise ValueError(f"verb={self.name} requires >=1 target_id; got {n}")

        return self


class RefuseReason(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: RefuseCategory
    message_hint: str = Field(min_length=1, max_length=120)


class JudgeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actions: list[Verb] | None = Field(default=None, max_length=4)
    refuse: RefuseReason | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "JudgeOutput":
        actions_set = self.actions is not None
        refuse_set = self.refuse is not None
        if actions_set == refuse_set:
            raise ValueError(
                f"JudgeOutput must set exactly one of {{actions, refuse}}; "
                f"got actions={actions_set}, refuse={refuse_set}"
            )
        if actions_set and len(self.actions) == 0:
            raise ValueError(
                "actions, if set, must contain >=1 verb (use 'wait' for no-op)"
            )
        return self
