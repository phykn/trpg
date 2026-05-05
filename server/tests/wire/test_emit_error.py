import json

from src.domain.errors import LLMUnavailable
from src.wire.emit import _to_snake, emit_error


def test_to_snake_acronym():
    assert _to_snake("LLMUnavailable") == "llm_unavailable"
    assert _to_snake("JSONDecodeError") == "json_decode_error"


def test_to_snake_simple_camel():
    assert _to_snake("NarrateMalformed") == "narrate_malformed"
    assert _to_snake("InvariantViolation") == "invariant_violation"


def test_emit_error_catalog_hit():
    ev = emit_error(LLMUnavailable("upstream timed out"))
    assert ev["type"] == "error"
    assert ev["data"]["code"] == "LLMUnavailable"
    assert ev["data"]["message"] == "이야기꾼이 잠시 길을 잃었습니다. 다시 시도해 주세요."


def test_emit_error_generic_fallback():
    ev = emit_error(RuntimeError("boom"))
    assert ev["type"] == "error"
    assert ev["data"]["code"] == "RuntimeError"
    assert ev["data"]["message"] == "지금은 응답할 수 없습니다. 잠시 후 다시 시도해 주세요."


def test_emit_error_serializable():
    ev = emit_error(LLMUnavailable("x"))
    json.dumps(ev, ensure_ascii=False)


def test_emit_error_strips_raw_message():
    raw = "Error code: 500 - [{'error': {'code': 500, 'message': 'Internal'}}]"
    ev = emit_error(LLMUnavailable(raw))
    text = ev["data"]["message"]
    assert "500" not in text
    assert "Error" not in text
    assert "Internal" not in text


def test_emit_error_jsondecodeerror_maps_via_catalog():
    err = json.JSONDecodeError("empty answer", "", 0)
    ev = emit_error(err)
    assert ev["data"]["code"] == "JSONDecodeError"
    assert ev["data"]["message"] == "행동을 해석하지 못했습니다. 다시 시도해 주세요."
