from src.db.graph_progress_rows import progress_from_row, progress_to_row
from src.game.domain.combat import GraphCombatState
from src.game.domain.progress import GameProgress
from src.game.domain.state import CombatState


def test_progress_row_round_trip():
    progress = GameProgress(
        game_id="game-1",
        player_id="player",
        locale="ko",
        active_subject_id="elder",
        active_quest_id="quest",
        turn_count=3,
        combat_state=CombatState(round=2, enemy_ids=["rat"]),
        next_log_id=9,
    )

    row = progress_to_row(progress)

    assert row.game_id == "game-1"
    assert row.progress["player_id"] == "player"
    assert row.progress["combat_state"]["round"] == 2

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
        enemy_ids=["rat"],
        participant_ids=["player", "rat"],
        sides={"player": "player", "rat": "enemy"},
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
    assert progress_from_row(row).graph_combat_state == graph_combat_state
