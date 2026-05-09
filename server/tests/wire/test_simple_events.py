import json

from src.wire.emit import emit_done, emit_narrative_delta, emit_suggestions
from src.wire.models import DonePayload, NarrativeDeltaPayload, SuggestionsPayload


# narrative_delta


def test_narrative_delta_envelope():
    ev = emit_narrative_delta("당신은 문 앞에 섰습니다.")
    assert ev["type"] == "narrative_delta"
    assert ev["data"] == {"text": "당신은 문 앞에 섰습니다."}


def test_narrative_delta_empty_text_allowed():
    """Empty chunks may legitimately appear during streaming."""
    ev = emit_narrative_delta("")
    assert ev["type"] == "narrative_delta"
    assert ev["data"] == {"text": ""}


def test_narrative_delta_serializable():
    ev = emit_narrative_delta("프로즈")
    s = json.dumps(ev, ensure_ascii=False)
    assert "프로즈" in s


# suggestions


def test_suggestions_envelope():
    ev = emit_suggestions(["문을 연다", "주위를 둘러본다"])
    assert ev["type"] == "suggestions"
    assert ev["data"] == {"items": ["문을 연다", "주위를 둘러본다"]}


def test_suggestions_empty_list_allowed():
    ev = emit_suggestions([])
    assert ev["data"] == {"items": []}


def test_suggestions_defensive_copy():
    """emit_suggestions copies the input list — caller mutation doesn't bleed."""
    src = ["a", "b"]
    ev = emit_suggestions(src)
    src.append("c")
    assert ev["data"]["items"] == ["a", "b"]


# done


def test_done_envelope():
    ev = emit_done()
    assert ev == {"type": "done", "data": {}}


def test_done_serializable():
    ev = emit_done()
    s = json.dumps(ev)
    assert s == '{"type": "done", "data": {}}'


# Construction sanity for all 3 models
def test_model_constructors():
    """Direct model construction for completeness."""
    n = NarrativeDeltaPayload(text="x")
    assert n.model_dump() == {"text": "x"}
    s = SuggestionsPayload(items=["a"])
    assert s.model_dump() == {"items": ["a"]}
    d = DonePayload()
    assert d.model_dump() == {}
