"""humanize_engine_error must always pick the most specific needle.

The phrase table holds substrings that overlap (e.g. "npc has not enough gold"
contains "not enough gold"). Without explicit ordering, the shorter prefix
could match first and surface the wrong Korean line. The implementation now
scans longest-needle-first; this test pins that contract.
"""
from src.flow.error_phrases import humanize_engine_error


def test_npc_gold_takes_priority_over_player_gold():
    err = ValueError("npc has not enough gold")
    assert humanize_engine_error(err) == "상대의 금화가 부족합니다"


def test_player_gold_still_matches_when_alone():
    err = ValueError("not enough gold")
    assert humanize_engine_error(err) == "금화가 부족합니다"


def test_unknown_message_falls_back():
    err = ValueError("totally unmapped engine error")
    assert humanize_engine_error(err) == "지금은 그 행동이 통하지 않습니다"
