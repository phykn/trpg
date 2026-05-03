"""Suggestion chips enforce detour action when free-path judge recently rejected."""

import pytest

from src.domain.entities import Character, Connection, Item, Location, Stats
from src.domain.state import GameState
from src.mapping.suggestion_chips import build_suggestion_chips


def _base_state() -> GameState:
    s = GameState(game_id="t", profile="default", player_id="player_01")
    s.locations["loc_a"] = Location(
        id="loc_a", name="주막", connections=[Connection(target_id="loc_b")]
    )
    s.locations["loc_b"] = Location(id="loc_b", name="광장")
    s.items["coin_01"] = Item(id="coin_01", name="증거 문서")
    s.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        gender="male",
        stats=Stats(),
        location_id="loc_a",
        inventory_ids=["coin_01"],
    )
    s.characters["npc_01"] = Character(
        id="npc_01",
        name="에드릭",
        race_id="human",
        gender="male",
        stats=Stats(),
        location_id="loc_a",
    )
    return s


def test_after_judge_rejected_first_chip_is_detour():
    state = _base_state()
    state.recent_engine_events.append(
        {"type": "judge_rejected", "quest_id": "q1", "reason": "근거 부족"}
    )
    chips = build_suggestion_chips(state)
    assert len(chips) >= 1
    # First chip is a detour, not the normal NPC talk chip.
    assert chips[0] not in ("에드릭에게 말을 건다",)
    assert "에드릭에게 말을 건다" not in chips


def test_after_judge_rejected_detour_chip_is_one_of_known_options():
    from src.mapping.suggestion_chips import _DETOUR_CHIPS

    state = _base_state()
    state.recent_engine_events.append(
        {"type": "judge_rejected", "quest_id": "q1", "reason": "근거 부족"}
    )
    chips = build_suggestion_chips(state)
    assert chips[0] in _DETOUR_CHIPS


def test_after_judge_rejected_non_npc_chips_still_present():
    """Location and inventory chips still appear alongside the detour chip."""
    state = _base_state()
    state.recent_engine_events.append(
        {"type": "judge_rejected", "quest_id": "q1", "reason": "근거 부족"}
    )
    chips = build_suggestion_chips(state)
    texts = " ".join(chips)
    assert "광장" in texts
    assert "증거 문서" in texts


def test_no_recent_rejection_normal_npc_chip():
    """Without a rejection event the NPC talk chip appears as usual."""
    state = _base_state()
    chips = build_suggestion_chips(state)
    assert "에드릭에게 말을 건다" in chips


def test_no_recent_rejection_no_detour_chip():
    from src.mapping.suggestion_chips import _DETOUR_CHIPS

    state = _base_state()
    chips = build_suggestion_chips(state)
    for chip in chips:
        assert chip not in _DETOUR_CHIPS


def test_repeated_rejections_rotate_detour_chip():
    from src.mapping.suggestion_chips import _DETOUR_CHIPS

    state = _base_state()
    state.recent_engine_events.append(
        {"type": "judge_rejected", "quest_id": "q1", "reason": ""}
    )
    chips_first = build_suggestion_chips(state)

    state.recent_engine_events.append(
        {"type": "judge_rejected", "quest_id": "q1", "reason": ""}
    )
    chips_second = build_suggestion_chips(state)

    # Both are valid detour chips.
    assert chips_first[0] in _DETOUR_CHIPS
    assert chips_second[0] in _DETOUR_CHIPS
    # Second rejection cycles to a different option.
    assert chips_first[0] != chips_second[0]
