from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.wire.graph.to_front import GraphFrontStatePayload

from .action.dispatch import GraphActionDispatchResult
from .state import GameRuntimeState
from .narration.suggestions import GraphSuggestion


GraphRequestStatus = Literal[
    "executed",
    "confirmation_required",
    "roll_required",
    "cancelled",
    "answered",
    "rejected",
]
GraphResultOutcome = Literal["success", "failure", "neutral"]


class GraphActionRequestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime: GameRuntimeState
    status: GraphRequestStatus
    outcome: GraphResultOutcome = "neutral"
    front_state: GraphFrontStatePayload
    pending_confirmation: dict[str, Any] | None = None
    pending_roll: dict[str, Any] | None = None
    dispatch: GraphActionDispatchResult | None = None
    message: str | None = None
    suggestions: list[GraphSuggestion] = Field(default_factory=list)


def executed_result(
    runtime: GameRuntimeState,
    front_state: GraphFrontStatePayload,
    *,
    dispatch: GraphActionDispatchResult | None = None,
    outcome: GraphResultOutcome = "success",
    suggestions: list[GraphSuggestion] | None = None,
) -> GraphActionRequestResult:
    return _result(
        runtime=runtime,
        status="executed",
        outcome=outcome_from_dispatch(dispatch) if dispatch is not None else outcome,
        front_state=front_state,
        dispatch=dispatch,
        suggestions=suggestions,
    )


def rejected_result(
    runtime: GameRuntimeState,
    front_state: GraphFrontStatePayload,
    message: str | None = None,
    *,
    suggestions: list[GraphSuggestion] | None = None,
) -> GraphActionRequestResult:
    return _result(
        runtime=runtime,
        status="rejected",
        outcome="failure",
        front_state=front_state,
        message=message,
        suggestions=suggestions,
    )


def answered_result(
    runtime: GameRuntimeState,
    front_state: GraphFrontStatePayload,
    message: str,
) -> GraphActionRequestResult:
    return _result(
        runtime=runtime,
        status="answered",
        outcome="neutral",
        front_state=front_state,
        message=message,
    )


def roll_required_result(
    runtime: GameRuntimeState,
    front_state: GraphFrontStatePayload,
    pending_roll: dict[str, Any],
) -> GraphActionRequestResult:
    return _result(
        runtime=runtime,
        status="roll_required",
        outcome="neutral",
        front_state=front_state,
        pending_roll=pending_roll,
    )


def confirmation_required_result(
    runtime: GameRuntimeState,
    front_state: GraphFrontStatePayload,
    pending_confirmation: dict[str, Any],
) -> GraphActionRequestResult:
    return _result(
        runtime=runtime,
        status="confirmation_required",
        outcome="neutral",
        front_state=front_state,
        pending_confirmation=pending_confirmation,
    )


def cancelled_result(
    runtime: GameRuntimeState,
    front_state: GraphFrontStatePayload,
) -> GraphActionRequestResult:
    return _result(
        runtime=runtime,
        status="cancelled",
        outcome="neutral",
        front_state=front_state,
    )


def outcome_from_dispatch(dispatch: GraphActionDispatchResult) -> GraphResultOutcome:
    if dispatch.kind == "combat":
        if dispatch.outcome == "victory":
            return "success"
        if dispatch.outcome == "defeat":
            return "failure"
        state = dispatch.runtime.progress.graph_combat_state
        if (
            state is not None
            and state.last_roll is not None
            and state.last_dc is not None
        ):
            return "success" if state.last_roll >= state.last_dc else "failure"
        return "neutral"
    if dispatch.kind == "move":
        return "neutral"
    return "neutral"


def _result(
    runtime: GameRuntimeState,
    front_state: GraphFrontStatePayload,
    *,
    status: GraphRequestStatus,
    outcome: GraphResultOutcome,
    pending_confirmation: dict[str, Any] | None = None,
    pending_roll: dict[str, Any] | None = None,
    dispatch: GraphActionDispatchResult | None = None,
    message: str | None = None,
    suggestions: list[GraphSuggestion] | None = None,
) -> GraphActionRequestResult:
    return GraphActionRequestResult(
        runtime=runtime,
        status=status,
        outcome=outcome,
        front_state=front_state,
        pending_confirmation=pending_confirmation,
        pending_roll=pending_roll,
        dispatch=dispatch,
        message=message,
        suggestions=suggestions or [],
    )
