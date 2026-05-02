"""humanize_engine_error must always pick the most specific needle.

The phrase table holds substrings that overlap (e.g. "npc has not enough gold"
contains "not enough gold"). Without explicit ordering, the shorter prefix
could match first and surface the wrong Korean line. The implementation now
scans longest-needle-first; this test pins that contract.
"""

from src.flow.error_phrases import humanize_engine_error, humanize_runtime_error


def test_npc_gold_takes_priority_over_player_gold():
    err = ValueError("npc has not enough gold")
    assert humanize_engine_error(err) == "상대의 금화가 부족합니다"


def test_player_gold_still_matches_when_alone():
    err = ValueError("not enough gold")
    assert humanize_engine_error(err) == "금화가 부족합니다"


def test_unknown_message_falls_back():
    err = ValueError("totally unmapped engine error")
    assert humanize_engine_error(err) == "지금은 그 행동이 통하지 않습니다"


# --- humanize_runtime_error: SSE error event sanitization -------------------


class JudgeMalformed(Exception):
    pass


class PersistenceFailed(Exception):
    pass


class LLMUnavailable(Exception):
    pass


def test_runtime_error_known_class_maps_to_korean():
    # The keys live in the source dict by class name string, so the test
    # types only need to match by `__name__` — they don't have to be the
    # real domain types.
    assert "행동을 해석" in humanize_runtime_error(JudgeMalformed("raw english trace"))
    assert "저장" in humanize_runtime_error(PersistenceFailed("postgrest 503"))
    assert "이야기꾼" in humanize_runtime_error(LLMUnavailable("upstream 500"))


def test_runtime_error_strips_raw_message():
    # The raw English / upstream API JSON must not leak into the user-facing
    # phrase. This is the whole point of the function — a Gemini 500 dump
    # like "Error code: 500 - [{'error': {...}}]" would be unreadable.
    raw = "Error code: 500 - [{'error': {'code': 500, 'message': 'Internal'}}]"
    out = humanize_runtime_error(LLMUnavailable(raw))
    assert "500" not in out
    assert "Error" not in out
    assert "Internal" not in out


def test_runtime_error_unknown_class_falls_back():
    err = RuntimeError("something we never planned for")
    out = humanize_runtime_error(err)
    assert "지금은" in out
    assert "something" not in out
