"""D2 fix — recent_dialogue narrator truncation in history layer.

Long narrator bodies fed verbatim into the prompt cause the LLM to
verbatim-echo them as prefix in the next turn. Truncating the narrator
to its opening 1-2 sentences (around 80-120 chars) before injection
keeps enough context for continuity without inviting verbatim reuse.
"""

from src.llm.context.layers import (
    _DIALOGUE_NARRATOR_MAX_CHARS,
    _format_dialogue_entry,
    _truncate_narrator,
)


def test_short_narrator_passes_through_unchanged():
    """Narrator already short enough — no truncation, no ellipsis."""
    s = "당신은 광장에 도착합니다."
    assert _truncate_narrator(s) == s


def test_long_narrator_cut_at_sentence_boundary():
    """Long narrator — cut at the end of the first/second sentence so the
    string ends with `.` or `다.` and doesn't dangle mid-clause."""
    s = (
        "당신은 새벽의 광장에 발을 들입니다. "
        "안개가 낮게 깔린 채 분수대가 메마른 침묵을 지킵니다. "
        "촌장이 분수대 옆에서 당신을 기다리는 듯합니다. "
        "마을 망루 너머에서 차가운 바람이 불어옵니다. "
        "당신은 어느 쪽으로 발길을 옮길지 결정해야 합니다."
    )
    out = _truncate_narrator(s)
    assert len(out) < len(s)
    # Truncated output ends at a sentence boundary marker (period before the
    # appended ellipsis), so without the marker it would end with `.`.
    stripped = out.rstrip("…").rstrip()
    assert stripped.endswith(".")
    # contains at most ~2 sentences worth (count by trailing periods)
    assert out.count(".") <= 3  # tolerate up to 2 mid + trailing


def test_truncated_marker_indicates_cut():
    """When cut, the result ends with an ellipsis marker so the LLM sees
    the input is partial."""
    s = "첫 문장입니다. 두 번째 문장입니다. " * 6  # ~120 chars, guaranteed > 80
    out = _truncate_narrator(s)
    assert len(out) < len(s)
    assert out.endswith("…")


def test_format_dialogue_entry_uses_truncated_narrator():
    """The user-facing helper threads through truncation."""
    long_narrator = "긴 본문이 들어옵니다. 첫 문장. 두 번째 문장. 세 번째 문장. " * 5
    line = _format_dialogue_entry(
        turn=12, player="앞으로 간다", narrator_redacted=long_narrator
    )
    # The full long_narrator should NOT appear verbatim in the output
    assert long_narrator not in line
    # But some prefix of it should
    assert long_narrator[:20] in line


def test_no_sentence_boundary_falls_back_to_char_cap():
    """A pathological no-sentence-end input still gets capped at the char
    limit so the prompt doesn't blow up."""
    s = "마침표 없는 매우 긴 문장이 끝없이 이어지고 있는 상황입니다 " * 20
    out = _truncate_narrator(s)
    # +1 for the appended "…" character
    assert len(out) <= _DIALOGUE_NARRATOR_MAX_CHARS + 1
