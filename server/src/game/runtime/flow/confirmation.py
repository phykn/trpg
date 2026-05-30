from collections.abc import AsyncIterator
from typing import Literal

from src.db.repo import GraphRepo, ScenarioRepo
from src.game.domain.action import Action
from src.llm.client import LLMClient
from src.llm.diag import engine_diag, set_diag_context
from src.wire.graph.to_front import graph_to_front_state

from ..load import load_runtime_state
from ..request_result import (
    GraphActionRequestResult,
    cancelled_result,
    confirmation_required_result,
    executed_result,
)
from ..pending_action import load_pending_action
from ..roll.gate import should_start_graph_roll
from .confirmation_policy import (
    build_graph_action_confirmation,
    requires_roll_after_confirmation,
)
from .turn import (
    GraphActionTurnError,
    run_graph_action_turn,
    run_graph_action_turn_from_runtime,
    run_graph_action_turn_from_runtime_stream,
)


Decision = Literal["confirm", "cancel"]


class GraphConfirmationError(ValueError):
    pass


class GraphConfirmationActive(GraphConfirmationError):
    pass


class GraphConfirmationExpected(GraphConfirmationError):
    pass


# Public flow


async def run_graph_action_request(
    repo: GraphRepo,
    game_id: str,
    action: Action,
    *,
    llm: LLMClient | None = None,
    player_input: str | None = None,
    scenario_repo: ScenarioRepo | None = None,
) -> GraphActionRequestResult:
    runtime = await load_runtime_state(repo, game_id, scenario_repo)
    set_diag_context(game_id, runtime.progress.turn_count)
    engine_diag("action:start", action=action.verb)
    if runtime.progress.pending_confirmation is not None:
        raise GraphConfirmationActive(
            "a pending_confirmation is already active; call graph confirm instead"
        )
    if runtime.progress.pending_roll is not None:
        raise GraphConfirmationActive(
            "a pending_roll is already active; call graph roll instead"
        )

    if should_start_graph_roll(runtime, action):
        from .roll import start_graph_roll

        engine_diag("action:roll_required", action=action.verb)
        return await start_graph_roll(
            repo, game_id, action, scenario_repo=scenario_repo
        )

    pending = build_graph_action_confirmation(runtime, action)
    if pending is None:
        result = await run_graph_action_turn(
            repo,
            game_id,
            action,
            llm=llm,
            player_input=player_input,
            scenario_repo=scenario_repo,
        )
        engine_diag("action:done", status="executed", action=action.verb)
        return executed_result(
            result.runtime,
            result.front_state,
            dispatch=result.dispatch,
            suggestions=result.suggestions,
        )

    next_progress = runtime.progress.model_copy(
        update={"pending_confirmation": pending}
    )
    next_runtime = runtime.model_copy(update={"progress": next_progress})
    await repo.save_progress(next_progress)
    engine_diag(
        "action:done",
        status="confirmation_required",
        action=action.verb,
        confirmation=pending.get("kind"),
    )
    return confirmation_required_result(
        next_runtime,
        graph_to_front_state(next_runtime),
        pending,
    )


async def run_graph_action_request_stream(
    repo: GraphRepo,
    game_id: str,
    action: Action,
    *,
    llm: LLMClient | None = None,
    player_input: str | None = None,
    scenario_repo: ScenarioRepo | None = None,
) -> AsyncIterator[dict[str, object]]:
    runtime = await load_runtime_state(repo, game_id, scenario_repo)
    set_diag_context(game_id, runtime.progress.turn_count)
    engine_diag("action:start", action=action.verb)
    if runtime.progress.pending_confirmation is not None:
        raise GraphConfirmationActive(
            "a pending_confirmation is already active; call graph confirm instead"
        )
    if runtime.progress.pending_roll is not None:
        raise GraphConfirmationActive(
            "a pending_roll is already active; call graph roll instead"
        )

    if should_start_graph_roll(runtime, action):
        from .roll import run_graph_preroll_stream

        engine_diag("action:roll_required", action=action.verb)
        async for event in run_graph_preroll_stream(
            llm,
            repo,
            game_id,
            action,
            scenario_repo=scenario_repo,
        ):
            yield event
        return

    pending = build_graph_action_confirmation(runtime, action)
    if pending is None:
        async for event in run_graph_action_turn_from_runtime_stream(
            repo,
            game_id,
            runtime,
            action,
            llm=llm,
            player_input=player_input,
        ):
            if event["type"] == "final":
                engine_diag("action:done", status="executed", action=action.verb)
            yield event
        return

    next_progress = runtime.progress.model_copy(
        update={"pending_confirmation": pending}
    )
    next_runtime = runtime.model_copy(update={"progress": next_progress})
    await repo.save_progress(next_progress)
    engine_diag(
        "action:done",
        status="confirmation_required",
        action=action.verb,
        confirmation=pending.get("kind"),
    )
    result = confirmation_required_result(
        next_runtime,
        graph_to_front_state(next_runtime),
        pending,
    )
    yield {"type": "result", "result": result}
    yield {"type": "final", "result": result}


async def run_graph_confirm(
    repo: GraphRepo,
    game_id: str,
    confirmation_id: str,
    decision: Decision,
    *,
    llm: LLMClient | None = None,
    scenario_repo: ScenarioRepo | None = None,
) -> GraphActionRequestResult:
    runtime = await load_runtime_state(repo, game_id, scenario_repo)
    set_diag_context(game_id, runtime.progress.turn_count)
    pending = runtime.progress.pending_confirmation
    engine_diag(
        "confirm:start",
        decision=decision,
        pending=pending.get("kind") if isinstance(pending, dict) else None,
    )
    if pending is None:
        raise GraphConfirmationExpected("no pending_confirmation")
    if pending.get("id") != confirmation_id:
        raise GraphConfirmationExpected("confirmation id mismatch")

    cleared_progress = runtime.progress.model_copy(
        update={"pending_confirmation": None}
    )
    cleared_runtime = runtime.model_copy(update={"progress": cleared_progress})
    if decision == "cancel":
        await repo.save_progress(cleared_progress)
        engine_diag("confirm:done", status="cancelled")
        return cancelled_result(
            cleared_runtime,
            graph_to_front_state(cleared_runtime),
        )

    action = load_pending_action(pending, error_type=GraphConfirmationExpected)
    if requires_roll_after_confirmation(action):
        await repo.save_progress(cleared_progress)
        from .roll import start_graph_roll

        result = await start_graph_roll(
            repo,
            game_id,
            action,
            scenario_repo=scenario_repo,
        )
        engine_diag("confirm:done", status="roll_required")
        return result

    try:
        result = await run_graph_action_turn_from_runtime(
            repo,
            game_id,
            cleared_runtime,
            action,
            llm=llm,
        )
    except GraphActionTurnError as exc:
        raise GraphConfirmationError(str(exc)) from exc
    engine_diag("confirm:done", status="executed")
    return executed_result(
        result.runtime,
        result.front_state,
        dispatch=result.dispatch,
        suggestions=result.suggestions,
    )


async def run_graph_confirm_stream(
    repo: GraphRepo,
    game_id: str,
    confirmation_id: str,
    decision: Decision,
    *,
    llm: LLMClient | None = None,
    scenario_repo: ScenarioRepo | None = None,
) -> AsyncIterator[dict[str, object]]:
    runtime = await load_runtime_state(repo, game_id, scenario_repo)
    set_diag_context(game_id, runtime.progress.turn_count)
    pending = runtime.progress.pending_confirmation
    engine_diag(
        "confirm:start",
        decision=decision,
        pending=pending.get("kind") if isinstance(pending, dict) else None,
    )
    if pending is None:
        raise GraphConfirmationExpected("no pending_confirmation")
    if pending.get("id") != confirmation_id:
        raise GraphConfirmationExpected("confirmation id mismatch")

    cleared_progress = runtime.progress.model_copy(
        update={"pending_confirmation": None}
    )
    cleared_runtime = runtime.model_copy(update={"progress": cleared_progress})
    if decision == "cancel":
        await repo.save_progress(cleared_progress)
        engine_diag("confirm:done", status="cancelled")
        result = cancelled_result(
            cleared_runtime,
            graph_to_front_state(cleared_runtime),
        )
        yield {"type": "result", "result": result}
        yield {"type": "final", "result": result}
        return

    action = load_pending_action(pending, error_type=GraphConfirmationExpected)
    if requires_roll_after_confirmation(action):
        await repo.save_progress(cleared_progress)
        from .roll import run_graph_preroll_stream

        engine_diag("confirm:done", status="roll_required")
        async for event in run_graph_preroll_stream(
            llm,
            repo,
            game_id,
            action,
            scenario_repo=scenario_repo,
        ):
            yield event
        return

    try:
        async for event in run_graph_action_turn_from_runtime_stream(
            repo,
            game_id,
            cleared_runtime,
            action,
            llm=llm,
        ):
            if event["type"] == "final":
                engine_diag("confirm:done", status="executed")
            yield event
    except GraphActionTurnError as exc:
        raise GraphConfirmationError(str(exc)) from exc
