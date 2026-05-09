from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from src.game.domain.action import Action
from src.game.domain.combat import GraphCombatAction, GraphCombatState
from src.game.engines.graph_combat import (
    GraphCombatError,
    GraphCombatResult,
    plan_combat_exchange,
    plan_combat_start,
)

from .apply import GraphRuntimeApplyError, apply_runtime_graph_changes
from .state import GameRuntimeState


class GraphCombatDispatchError(ValueError):
    pass


class GraphCombatDispatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime: GameRuntimeState
    combat: GraphCombatResult
    outcome: str
    started: bool
    applied: int


def dispatch_graph_combat_action(
    runtime: GameRuntimeState,
    action: Action,
) -> GraphCombatDispatchResult:
    try:
        state, started = _resolve_state(runtime, action)
        combat_action = _combat_action_from_action(action, in_combat=not started)
        combat_result = plan_combat_exchange(
            runtime.graph,
            state,
            runtime.progress.player_id,
            combat_action,
        )
        applied = apply_runtime_graph_changes(runtime, combat_result.changes)
    except (GraphCombatError, GraphRuntimeApplyError) as exc:
        raise GraphCombatDispatchError(str(exc)) from exc

    graph_runtime = applied.runtime
    next_progress = graph_runtime.progress.model_copy(
        update={
            "graph_combat_state": (
                combat_result.state if combat_result.state.outcome == "ongoing" else None
            )
        }
    )
    next_runtime = graph_runtime.model_copy(update={"progress": next_progress})
    return GraphCombatDispatchResult(
        runtime=next_runtime,
        combat=combat_result,
        outcome=combat_result.state.outcome,
        started=started,
        applied=applied.applied,
    )


def _resolve_state(
    runtime: GameRuntimeState,
    action: Action,
) -> tuple[GraphCombatState, bool]:
    state = runtime.progress.graph_combat_state
    if state is not None:
        return state, False

    if action.verb not in ("attack", "cast"):
        raise GraphCombatDispatchError(f"cannot start graph combat with {action.verb}")

    target_id = _target_id_for_start(action)
    try:
        result = plan_combat_start(runtime.graph, runtime.progress.player_id, target_id)
    except GraphCombatError as exc:
        raise GraphCombatDispatchError(str(exc)) from exc
    return result.state, True


def _combat_action_from_action(action: Action, *, in_combat: bool) -> GraphCombatAction:
    if action.verb == "attack":
        skill_id = _single(action.with_)
        return GraphCombatAction(
            kind="cast" if skill_id else "attack",
            target_id=_single(action.what),
            skill_id=skill_id,
        )
    if action.verb == "cast":
        return GraphCombatAction(
            kind="cast",
            target_id=_single(action.to),
            skill_id=_single(action.with_) or _single(action.what),
        )
    if in_combat and action.verb == "move" and action.how in ("flee", "hasty"):
        return GraphCombatAction(kind="flee")
    if in_combat and action.verb == "pass":
        return GraphCombatAction(kind="defend")
    raise GraphCombatDispatchError(f"unsupported graph combat action: {action.verb}")


def _target_id_for_start(action: Action) -> str:
    if action.verb == "attack":
        target_id = _single(action.what)
    elif action.verb == "cast":
        target_id = _single(action.to)
    else:
        target_id = None
    if target_id is None:
        raise GraphCombatDispatchError("graph combat target is required")
    return target_id


def _single(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value and isinstance(value[0], str):
        return value[0]
    return None
