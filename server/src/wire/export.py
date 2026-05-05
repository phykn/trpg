import json
import re
from pathlib import Path

from .models.error import ErrorPayload
from .models.hero import HeroPayload
from .models.pending_check import PendingCheckPayload

_MODELS = [ErrorPayload, PendingCheckPayload, HeroPayload]


def _flatten(schema: dict, definitions: dict) -> dict:
    """Hoist Pydantic-v2 $defs into the bundle definitions and rewrite $refs.

    Pydantic v2 places nested-model schemas in a per-model $defs block and
    emits $ref: "#/$defs/Name". The draft-07 bundle uses definitions at the
    root, so we must lift those entries up and rewrite the refs accordingly.
    """
    nested = schema.pop("$defs", {})
    for name, sub in nested.items():
        definitions[name] = sub
    raw = json.dumps(schema)
    fixed = re.sub(r'"#/\$defs/', '"#/definitions/', raw)
    return json.loads(fixed)


def dump_schemas(out_path: Path) -> None:
    definitions: dict = {}
    for m in _MODELS:
        definitions[m.__name__] = _flatten(m.model_json_schema(), definitions)
    bundle = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "definitions": definitions,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
