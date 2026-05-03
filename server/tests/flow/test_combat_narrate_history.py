"""combat_narrate input includes the last 5 turn_log summaries and the last
2 dialogue pairs as build-up context. Without these, the cinematic can't
reflect a setup beat (e.g. distraction, trap, bait) that motivated the
opening of the fight."""

import pytest

from src.domain.entities import Character, Location, Stats
from src.domain.memory import DialoguePair, TurnLogEntry
from src.domain.state import CombatState
from src.flow.combat_auto import (
    AutoCombatResult,
    build_narrate_input,
)
from src.llm_calls.combat_narrate.schema import PlayerNarrateSnapshot
from src.persistence.local_fs import LocalFsScenarioRepo


@pytest.fixture
def state_with_log(fresh_state):
    fresh_state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        location_id="plaza_01",
        stats=Stats(),
    )
    fresh_state.combat_state = CombatState(
        turn_order=["player_01"], enemy_ids=[], round=1
    )
    for i in range(7):
        fresh_state.turn_log.append(
            TurnLogEntry(turn=i + 1, target=None, summary=f"summary_{i + 1}")
        )
    for i in range(3):
        fresh_state.recent_dialogue.append(
            DialoguePair(turn=i + 1, player=f"p_{i + 1}", narrator=f"n_{i + 1}")
        )
    return fresh_state


async def test_history_and_dialogue_truncated_to_last_window(state_with_log):
    """history → last 5 turn_log summaries; recent_dialogue → last 2 pairs.
    Order is oldest→newest so round 1 prose can read them as build-up."""
    result = AutoCombatResult(
        events=[],
        rounds_run=1,
        outcome="victory",
        player_start=PlayerNarrateSnapshot(name="주인공", alive=True),
    )
    input_ = await build_narrate_input(
        state_with_log,
        LocalFsScenarioRepo(profile_dir="<unused>"),
        player_input="공격",
        result=result,
    )

    assert len(input_.history) == 5
    assert [h["summary"] for h in input_.history] == [
        "summary_3",
        "summary_4",
        "summary_5",
        "summary_6",
        "summary_7",
    ]
    assert all({"turn", "target", "summary"} <= set(h.keys()) for h in input_.history)

    assert len(input_.recent_dialogue) == 2
    assert [d["player"] for d in input_.recent_dialogue] == ["p_2", "p_3"]
    assert all(
        {"turn", "player", "narrator"} <= set(d.keys()) for d in input_.recent_dialogue
    )


async def test_empty_log_yields_empty_lists(fresh_state):
    """No turn_log / recent_dialogue → empty lists, not missing fields."""
    fresh_state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        location_id="plaza_01",
        stats=Stats(),
    )
    fresh_state.combat_state = CombatState(
        turn_order=["player_01"], enemy_ids=[], round=1
    )

    result = AutoCombatResult(
        events=[],
        rounds_run=1,
        outcome="victory",
        player_start=PlayerNarrateSnapshot(name="주인공", alive=True),
    )
    input_ = await build_narrate_input(
        fresh_state,
        LocalFsScenarioRepo(profile_dir="<unused>"),
        player_input="공격",
        result=result,
    )

    assert input_.history == []
    assert input_.recent_dialogue == []
