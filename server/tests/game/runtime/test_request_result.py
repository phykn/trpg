from typing import get_args

from src.game.domain.combat import GraphCombatState
from src.game.domain.progress import GameProgress
from src.game.domain.graph import Graph, GraphNode
from src.game.runtime.action.dispatch import GraphActionDispatchResult
from src.game.runtime.request_result import (
    GraphActionRequestResult,
    GraphRequestStatus,
    answered_result,
    cancelled_result,
    confirmation_required_result,
    executed_result,
    outcome_from_dispatch,
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
    assert confirmation.pending_confirmation == {
        "id": "confirm_1",
        "kind": "quest_accept",
    }
    assert confirmation.pending_roll is None
    assert roll.status == "roll_required"
    assert roll.pending_roll == {"id": "roll_1", "kind": "perceive"}
    assert roll.pending_confirmation is None


def test_result_helpers_set_response_level_outcome():
    runtime = _runtime()
    front_state = graph_to_front_state(runtime)

    assert executed_result(runtime, front_state).outcome == "success"
    assert rejected_result(runtime, front_state).outcome == "failure"
    assert (
        answered_result(runtime, front_state, "주변은 조용합니다.").outcome == "neutral"
    )
    assert cancelled_result(runtime, front_state).outcome == "neutral"
    assert (
        confirmation_required_result(
            runtime,
            front_state,
            {"id": "confirm_1", "kind": "quest_accept"},
        ).outcome
        == "neutral"
    )
    assert (
        roll_required_result(
            runtime,
            front_state,
            {"id": "roll_1", "kind": "perceive"},
        ).outcome
        == "neutral"
    )


def test_outcome_from_dispatch_maps_combat_and_move_results():
    runtime = _runtime()

    def dispatch(kind: str, outcome: str | None = None) -> GraphActionDispatchResult:
        return GraphActionDispatchResult(
            runtime=runtime,
            kind=kind,
            applied=0,
            changed_node_ids=[],
            changed_edge_ids=[],
            removed_edge_ids=[],
            outcome=outcome,
        )

    assert outcome_from_dispatch(dispatch("combat", "victory")) == "success"
    assert outcome_from_dispatch(dispatch("combat", "defeat")) == "failure"
    assert outcome_from_dispatch(dispatch("combat", "escaped")) == "neutral"
    assert outcome_from_dispatch(dispatch("move")) == "neutral"
    assert outcome_from_dispatch(dispatch("quest_accept")) == "neutral"

    combat_runtime = runtime.model_copy(
        update={
            "progress": runtime.progress.model_copy(
                update={
                    "graph_combat_state": GraphCombatState(
                        location_id="town",
                        player_id="player_01",
                        active_enemy_id="goblin_01",
                        enemy_ids=["goblin_01"],
                        participant_ids=["player_01", "goblin_01"],
                        sides={"player_01": "player", "goblin_01": "enemy"},
                        last_roll=15,
                        last_dc=11,
                    )
                }
            )
        }
    )
    assert (
        outcome_from_dispatch(
            GraphActionDispatchResult(
                runtime=combat_runtime,
                kind="combat",
                applied=0,
                changed_node_ids=[],
                changed_edge_ids=[],
                removed_edge_ids=[],
                outcome="ongoing",
            )
        )
        == "success"
    )


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
