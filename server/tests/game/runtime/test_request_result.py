from typing import get_args

from src.game.domain.progress import GameProgress
from src.game.domain.graph import Graph, GraphNode
from src.game.runtime.request_result import (
    GraphActionRequestResult,
    GraphRequestStatus,
    answered_result,
    cancelled_result,
    confirmation_required_result,
    executed_result,
    rejected_result,
    roll_required_result,
)
from src.game.runtime.state import GameRuntimeState
from src.wire.graph.to_front import graph_to_front_state


def _runtime() -> GameRuntimeState:
    return GameRuntimeState(
        graph=Graph(
            nodes={
                "player_01": GraphNode(
                    id="player_01",
                    type="character",
                    properties={
                        "name": "테스터",
                        "hp": 10,
                        "max_hp": 10,
                        "mp": 5,
                        "max_mp": 5,
                        "alive": True,
                        "stats": {
                            "body": 10,
                            "agility": 10,
                            "mind": 10,
                            "presence": 10,
                        },
                    },
                )
            }
        ),
        progress=GameProgress(game_id="game-1", player_id="player_01"),
    )


def test_request_status_literals_are_the_api_status_set():
    assert set(get_args(GraphRequestStatus)) == {
        "executed",
        "rejected",
        "answered",
        "roll_required",
        "confirmation_required",
        "cancelled",
    }


def test_result_helpers_set_only_the_relevant_pending_payload():
    runtime = _runtime()
    front_state = graph_to_front_state(runtime)

    confirmation = confirmation_required_result(
        runtime,
        front_state,
        {"id": "confirm_1", "kind": "quest_accept"},
    )
    roll = roll_required_result(
        runtime,
        front_state,
        {"id": "roll_1", "kind": "perceive"},
    )

    assert confirmation.status == "confirmation_required"
    assert confirmation.pending_confirmation == {"id": "confirm_1", "kind": "quest_accept"}
    assert confirmation.pending_roll is None
    assert roll.status == "roll_required"
    assert roll.pending_roll == {"id": "roll_1", "kind": "perceive"}
    assert roll.pending_confirmation is None


def test_terminal_result_helpers_keep_existing_response_shape():
    runtime = _runtime()
    front_state = graph_to_front_state(runtime)

    results = [
        executed_result(runtime, front_state),
        answered_result(runtime, front_state, "주변은 조용합니다."),
        rejected_result(runtime, front_state, "지금은 할 수 없습니다."),
        cancelled_result(runtime, front_state),
    ]

    assert [result.status for result in results] == [
        "executed",
        "answered",
        "rejected",
        "cancelled",
    ]
    assert results[1].message == "주변은 조용합니다."
    assert results[2].message == "지금은 할 수 없습니다."
    assert all(isinstance(result, GraphActionRequestResult) for result in results)


def test_runtime_package_reexports_request_result():
    from src.game.runtime import GraphActionRequestResult
    from src.game.runtime.request_result import GraphActionRequestResult as Direct

    assert GraphActionRequestResult is Direct
