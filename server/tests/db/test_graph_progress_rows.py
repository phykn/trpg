import pytest
from pydantic import ValidationError

from src.db.graph_progress_rows import (
    GameProgressRow,
    progress_from_row,
    progress_to_row,
)
from src.game.domain.combat import GraphCombatState
from src.game.domain.progress import GameProgress


def test_progress_row_round_trip():
    progress = GameProgress(
        game_id="game-1",
        player_id="player",
        locale="ko",
        active_subject_id="elder",
        active_quest_id="quest",
        turn_count=3,
        next_log_id=9,
    )

    row = progress_to_row(progress)

    assert row.game_id == "game-1"
    assert row.progress["player_id"] == "player"

    restored = progress_from_row(row)

    assert restored == progress


def test_progress_row_accepts_pending_confirmation_payload():
    progress = GameProgress(
        game_id="game-1",
        player_id="player",
        pending_confirmation={
            "id": "confirm-1",
            "kind": "attack_start",
            "action": {"verb": "attack", "what": ["rat"]},
        },
    )

    restored = progress_from_row(progress_to_row(progress))

    assert restored.pending_confirmation["kind"] == "attack_start"


def test_progress_row_round_trips_graph_combat_state():
    graph_combat_state = GraphCombatState(
        location_id="town",
        player_id="player",
        active_enemy_id="rat",
        enemy_ids=["rat"],
        participant_ids=["player", "rat"],
        sides={"player": "player", "rat": "enemy"},
        player_hearts=2,
        enemy_hearts=1,
        round=2,
    )
    progress = GameProgress(
        game_id="game-1",
        player_id="player",
        graph_combat_state=graph_combat_state,
    )

    row = progress_to_row(progress)

    assert row.progress["graph_combat_state"]["round"] == 2
    assert row.progress["graph_combat_state"]["enemy_ids"] == ["rat"]
    assert row.progress["graph_combat_state"]["player_hearts"] == 2
    assert progress_from_row(row).graph_combat_state == graph_combat_state


def test_progress_from_row_backfills_legacy_graph_combat_state():
    row = GameProgressRow(
        game_id="game-1",
        progress={
            "player_id": "player",
            "graph_combat_state": {
                "location_id": "town",
                "player_id": "player",
                "enemy_ids": ["rat"],
                "participant_ids": ["player", "rat"],
                "sides": {"player": "player", "rat": "enemy"},
                "round": 2,
            },
        },
    )

    restored = progress_from_row(row)

    assert restored.graph_combat_state is not None
    assert restored.graph_combat_state.active_enemy_id == "rat"
    assert restored.graph_combat_state.player_hearts == 3
    assert restored.graph_combat_state.enemy_hearts == 3


def test_progress_rejects_removed_combat_state_field():
    with pytest.raises(ValidationError):
        GameProgress(
            game_id="game-1",
            player_id="player",
            combat_state={"round": 2, "enemy_ids": ["rat"]},
        )
