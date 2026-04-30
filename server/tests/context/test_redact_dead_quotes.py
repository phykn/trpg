"""Unit tests for `context.layers.redact_dead_quotes` — the pure helper that
strips Korean direct-quote blocks (`「…」` / `『…』`) attributed to a dead
NPC. The same helper feeds `build_history_layer` (input redaction) and
`consume_narrate` (output redaction).
"""
from src.context.layers import redact_dead_quotes


def test_empty_dead_names_returns_unchanged():
    assert redact_dead_quotes("그는 「잘 가시오.」라고 말합니다.", []) == \
        "그는 「잘 가시오.」라고 말합니다."


def test_empty_text_returns_unchanged():
    assert redact_dead_quotes("", ["노인"]) == ""


def test_name_then_quote_redacts():
    text = "노인이 고개를 비스듬히 합니다. 「자네는 늦었네.」"
    out = redact_dead_quotes(text, ["노인"])
    assert "「자네는 늦었네.」" not in out
    assert "…" in out


def test_name_with_particle_inside_window_redacts():
    # 노인이 (가/이 josa attached) — substring scan still finds "노인".
    text = "노인이 손을 들어 막습니다. 「그건 안 되네.」"
    out = redact_dead_quotes(text, ["노인"])
    assert "「" not in out
    assert "…" in out


def test_double_corner_bracket_also_redacts():
    text = "촌장이 잠시 입을 다뭅니다. 『더는 할 말이 없네.』"
    out = redact_dead_quotes(text, ["촌장"])
    assert "『" not in out
    assert "…" in out


def test_name_not_in_pre_window_keeps_quote():
    # Name is far away (>30 chars) before the quote — not attributed, keep.
    long_filler = "주변이 천천히 가라앉습니다. 빛은 점점 늘어지고, 공기가 차갑게 식어갑니다. 한참 뒤, "
    text = f"노인을 보고 떠납니다. {long_filler}「잘 지내시오.」"
    out = redact_dead_quotes(text, ["노인"])
    assert "「잘 지내시오.」" in out


def test_quote_with_live_npc_kept():
    # 상인 is alive (not in dead_names), so its quote stays.
    text = "상인이 미소를 짓습니다. 「오늘 좋은 물건이 있소.」"
    out = redact_dead_quotes(text, ["노인"])
    assert "「오늘 좋은 물건이 있소.」" in out


def test_mixed_quotes_only_dead_redacted():
    text = (
        "상인이 미소를 짓습니다. 「오늘 좋은 물건이 있소.」 "
        "노인이 고개를 비스듬히 합니다. 「자네는 늦었네.」"
    )
    out = redact_dead_quotes(text, ["노인"])
    assert "「오늘 좋은 물건이 있소.」" in out
    assert "「자네는 늦었네.」" not in out
    assert out.count("…") == 1


def test_unmatched_opener_preserves_remainder():
    # Truncated quote — leave as-is rather than swallow downstream text.
    text = "노인이 고개를 듭니다. 「말을 시작하다 끊어진다"
    out = redact_dead_quotes(text, ["노인"])
    assert out == text


def test_multiple_dead_names_any_match_redacts():
    text = "촌장이 한숨을 쉽니다. 「오래된 일이오.」 노인이 끼어듭니다. 「그만하시게.」"
    out = redact_dead_quotes(text, ["촌장", "노인"])
    assert "「" not in out
    assert out.count("…") == 2


def test_redact_marker_replaces_only_quote_block():
    text = "노인이 「가게」 안으로 들어섭니다."
    # 가게 inside quote — but quote is right after 노인, so it should redact.
    out = redact_dead_quotes(text, ["노인"])
    assert out == "노인이 … 안으로 들어섭니다."
