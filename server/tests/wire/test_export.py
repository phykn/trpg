import json
from pathlib import Path

from src.wire.export import dump_schemas


def test_dump_schemas_writes_error_payload(tmp_path: Path):
    out = tmp_path / "wire.schema.json"
    dump_schemas(out)
    bundle = json.loads(out.read_text(encoding="utf-8"))

    assert "definitions" in bundle
    assert "ErrorPayload" in bundle["definitions"]
    props = bundle["definitions"]["ErrorPayload"]["properties"]
    assert "code" in props
    assert "message" in props
    assert props["code"]["type"] == "string"
    assert props["message"]["type"] == "string"


def test_dump_schemas_includes_required(tmp_path: Path):
    out = tmp_path / "wire.schema.json"
    dump_schemas(out)
    bundle = json.loads(out.read_text(encoding="utf-8"))
    required = bundle["definitions"]["ErrorPayload"].get("required", [])
    assert set(required) == {"code", "message"}
