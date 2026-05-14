from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.wire.graph_to_front import GraphFrontStatePayload

from .dispatch import GraphActionDispatchResult
from .state import GameRuntimeState
from .suggestions import GraphSuggestionValue


GraphRequestStatus = Literal[
    "executed",
    "confirmation_required",
    "roll_required",
    "cancelled",
    "answered",
    "rejected",
]


class GraphActionRequestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime: GameRuntimeState
    status: GraphRequestStatus
    front_state: GraphFrontStatePayload
    pending_confirmation: dict[str, Any] | None = None
    pending_roll: dict[str, Any] | None = None
    dispatch: GraphActionDispatchResult | None = None
    message: str | None = None
    suggestions: list[GraphSuggestionValue] = Field(default_factory=list)


def executed_result(
    runtime: GameRuntimeState,
    front_state: GraphFrontStatePayload,
    *,
    dispatch: GraphActionDispatchResult | None = None,
    suggestions: list[GraphSuggestionValue] | None = None,
) -> GraphActionRequestResult:
    return _result(
        runtime=runtime,
        status="executed",
        front_state=front_state,
        dispatch=dispatch,
        suggestions=suggestions,
    )


def rejected_result(
    runtime: GameRuntimeState,
    front_state: GraphFrontStatePayload,
    message: str | None = None,
    *,
    suggestions: list[GraphSuggestionValue] | None = None,
) -> GraphActionRequestResult:
    return _result(
        runtime=runtime,
        status="rejected",
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
        front_state=front_state,
    )


def _result(
    runtime: GameRuntimeState,
    front_state: GraphFrontStatePayload,
    *,
    status: GraphRequestStatus,
    pending_confirmation: dict[str, Any] | None = None,
    pending_roll: dict[str, Any] | None = None,
    dispatch: GraphActionDispatchResult | None = None,
    message: str | None = None,
    suggestions: list[GraphSuggestionValue] | None = None,
) -> GraphActionRequestResult:
    return GraphActionRequestResult(
        runtime=runtime,
        status=status,
        front_state=front_state,
        pending_confirmation=pending_confirmation,
        pending_roll=pending_roll,
        dispatch=dispatch,
        message=message,
        suggestions=suggestions or [],
    )
