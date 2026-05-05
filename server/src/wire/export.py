import json
from pathlib import Path

from .models.error import ErrorPayload

_MODELS = [ErrorPayload]


def dump_schemas(out_path: Path) -> None:
    bundle = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "definitions": {m.__name__: m.model_json_schema() for m in _MODELS},
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
