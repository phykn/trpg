from dataclasses import dataclass, field
from typing import Any, Literal

from .errors import ModifierValidationError
from .schema import Verb, VerbName

TargetCardinality = Literal["forbidden", "optional", "required_one", "required_many"]


@dataclass(frozen=True)
class ModifierSchema:
    required_modifiers: frozenset[str] = frozenset()
    optional_modifiers: dict[str, type | tuple[Any, ...]] = field(default_factory=dict)
    target_cardinality: TargetCardinality = "forbidden"
    disjunctive_required: tuple[frozenset[str], ...] = ()


_MODIFIER_SCHEMAS: dict[VerbName, ModifierSchema] = {
    "move": ModifierSchema(
        required_modifiers=frozenset({"destination"}),
        optional_modifiers={
            "destination": str,
            "manner": ("normal", "stealthy", "hasty"),
            "tail_intent": str,
        },
        target_cardinality="forbidden",
    ),
    "transfer": ModifierSchema(
        required_modifiers=frozenset({"from_id", "to_id", "mode"}),
        optional_modifiers={
            "from_id": str,
            "to_id": str,
            "mode": ("gift", "trade", "steal"),
            "item_id": str,
            "price": int,
            "haggle": bool,
            "tail_intent": str,
        },
        target_cardinality="forbidden",
    ),
    "use": ModifierSchema(
        required_modifiers=frozenset({"item_id"}),
        optional_modifiers={"item_id": str, "target_id": str, "tail_intent": str},
        target_cardinality="forbidden",
    ),
    "attack": ModifierSchema(
        required_modifiers=frozenset(),
        optional_modifiers={
            "force": ("lethal", "subdue"),
            "surprise": bool,
            "skill_id": str,
            "ranged": bool,
            "tail_intent": str,
        },
        target_cardinality="required_many",
    ),
    "cast": ModifierSchema(
        required_modifiers=frozenset({"skill_id"}),
        optional_modifiers={"skill_id": str, "tail_intent": str},
        target_cardinality="optional",
    ),
    "speak": ModifierSchema(
        required_modifiers=frozenset({"intent"}),
        optional_modifiers={
            "intent": ("friendly", "hostile", "deceptive", "recruit", "part"),
            "target": str,
            "kind": ("companion", "alliance", "marriage", "query", "gossip"),
            "physical": ("verbal", "kneel", "song", "gesture", "embrace"),
            "topic": str,
            "claim": str,
            "tail_intent": str,
        },
        target_cardinality="forbidden",
    ),
    "perceive": ModifierSchema(
        required_modifiers=frozenset(),
        optional_modifiers={},
        target_cardinality="optional",
    ),
    "rest": ModifierSchema(
        required_modifiers=frozenset(),
        optional_modifiers={},
        target_cardinality="forbidden",
    ),
    "wait": ModifierSchema(
        required_modifiers=frozenset(),
        optional_modifiers={
            "tail_intent": str,
        },
        target_cardinality="forbidden",
    ),
}


def validate_modifiers(verb: Verb, *, in_combat: bool) -> None:
    """Mutates verb.modifiers in place to drop unknown keys (absorbs LLM hallucination).
    Raises ModifierValidationError on missing required, type/enum mismatch,
    target_ids cardinality violation, or unmet disjunctive_required."""
    schema = _MODIFIER_SCHEMAS.get(verb.name)
    if schema is None:
        raise ModifierValidationError(f"unknown verb: {verb.name}")

    allowed = schema.required_modifiers | set(schema.optional_modifiers.keys())
    for k in [k for k in verb.modifiers if k not in allowed]:
        verb.modifiers.pop(k)

    missing = schema.required_modifiers - set(verb.modifiers.keys())
    if verb.name == "move" and in_combat:
        missing -= {"destination"}
    if missing:
        raise ModifierValidationError(
            f"verb={verb.name} missing required modifiers: {sorted(missing)}"
        )

    for d_set in schema.disjunctive_required:
        if not (d_set & set(verb.modifiers.keys())):
            raise ModifierValidationError(
                f"verb={verb.name} requires at least one of: {sorted(d_set)}"
            )

    for k, v in verb.modifiers.items():
        spec = schema.optional_modifiers.get(k)
        if spec is None and k in schema.required_modifiers:
            spec = str
        if spec is None:
            continue
        if isinstance(spec, tuple):
            if v not in spec:
                raise ModifierValidationError(
                    f"verb={verb.name}.modifiers[{k}]={v!r} not in {spec}"
                )
        elif isinstance(spec, type):
            if not isinstance(v, spec):
                raise ModifierValidationError(
                    f"verb={verb.name}.modifiers[{k}]={v!r} not {spec.__name__}"
                )

    n = len(verb.target_ids)
    cardinality = schema.target_cardinality
    if cardinality == "forbidden" and n > 0:
        raise ModifierValidationError(
            f"verb={verb.name} forbids target_ids; got {n}"
        )
    if cardinality == "required_one" and n != 1:
        raise ModifierValidationError(
            f"verb={verb.name} requires exactly 1 target_id; got {n}"
        )
    if cardinality == "required_many" and n < 1:
        raise ModifierValidationError(
            f"verb={verb.name} requires >=1 target_id; got {n}"
        )
