from collections.abc import AsyncIterator, Sequence

from src.db.repo import GraphRepo, ScenarioRepo
from src.game.domain.action import Action, ActionCheckHint, ActionOutput
from src.game.domain.memory import PlayerLogEntry
from src.llm.calls.classify.runner import classify
from src.llm.calls.classify.schema import ClassifyInput
from src.llm.context.classify_view import (
    ClassifyContextLimits,
    build_classify_context_view,
)
from src.llm.client import LLMClient
from src.llm.diag import engine_diag, set_diag_context

from ...action_refs import first_ref
from ..confirmation import (
    GraphConfirmationActive,
    run_graph_action_request,
    run_graph_action_request_stream,
)
from .action_sequence import (
    check_hint_at,
    normalize_classified_action_sequence,
)
from .targets import with_implicit_speak_target as _with_implicit_speak_target
from ..roll import run_graph_preroll_stream
from ...load import load_runtime_state
from ...request_result import GraphActionRequestResult
from ...roll.gate import should_start_graph_roll
from ...state import GameRuntimeState
from ...env import env_nonnegative_int
from .narration import (
    run_graph_narrative_input,
    run_graph_narrative_input_stream,
    run_graph_refused_input,
    run_graph_refused_input_stream,
    run_graph_rejected_input,
    run_graph_rejected_input_stream,
)
from ..turn import GraphActionTurnError


class GraphInputError(ValueError):
    pass


def _classify_context_limits() -> ClassifyContextLimits:
    return ClassifyContextLimits(
        recent_scene=_classify_limit("RECENT_SCENE", 3),
        recent_exchanges=_classify_limit("RECENT_EXCHANGES", 3),
    )


def _classify_limit(name: str, default: int) -> int:
    return env_nonnegative_int(f"LLM_CLASSIFY_LIMIT_{name}", default)


# Public flow


async def run_graph_input_turn(
    client: LLMClient,
    repo: GraphRepo,
    game_id: str,
    player_input: str,
    scenario_repo: ScenarioRepo | None = None,
) -> GraphActionRequestResult:
    runtime, output = await _classify_player_input(
        client,
        repo,
        game_id,
        player_input,
        scenario_repo,
    )

    if output.refuse is not None:
        return await run_graph_refused_input(
            client,
            repo,
            runtime,
            player_input,
            output.refuse.message_hint,
            target=output.refuse.target,
        )
    actions = output.actions or []
    if not actions:
        raise GraphInputError("graph input requires at least one action")

    return await _run_classified_actions(
        client,
        repo,
        runtime,
        actions,
        output.action_checks,
        player_input,
        scenario_repo=scenario_repo,
    )


async def run_graph_input_turn_stream(
    client: LLMClient,
    repo: GraphRepo,
    game_id: str,
    player_input: str,
    scenario_repo: ScenarioRepo | None = None,
) -> AsyncIterator[dict[str, object]]:
    runtime, output = await _classify_player_input(
        client,
        repo,
        game_id,
        player_input,
        scenario_repo,
    )

    if output.refuse is not None:
        async for event in run_graph_refused_input_stream(
            client,
            repo,
            runtime,
            player_input,
            output.refuse.message_hint,
            target=output.refuse.target,
        ):
            yield event
        return
    actions = output.actions or []
    if not actions:
        raise GraphInputError("graph input requires at least one action")

    async for event in _run_classified_actions_stream(
        client,
        repo,
        runtime,
        actions,
        output.action_checks,
        player_input,
        scenario_repo=scenario_repo,
    ):
        yield event


async def _classify_player_input(
    client: LLMClient,
    repo: GraphRepo,
    game_id: str,
    player_input: str,
    scenario_repo: ScenarioRepo | None,
) -> tuple[GameRuntimeState, ActionOutput]:
    runtime = await load_runtime_state(repo, game_id, scenario_repo)
    _raise_if_pending_input_blocked(runtime)
    set_diag_context(game_id, runtime.progress.turn_count)
    engine_diag("input:start", chars=len(player_input))
    runtime = await _append_player_input_log(repo, runtime, player_input)
    output = await classify(
        client,
        ClassifyInput(
            player_input=player_input,
            context=build_classify_context_view(
                runtime,
                player_input,
                limits=_classify_context_limits(),
            ),
        ),
        locale=runtime.progress.locale,
    )
    return runtime, output


# Classified action dispatch


async def _run_classified_actions(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    actions: Sequence[Action],
    action_checks: Sequence[ActionCheckHint],
    player_input: str,
    *,
    scenario_repo: ScenarioRepo | None = None,
) -> GraphActionRequestResult:
    actions, action_checks = normalize_classified_action_sequence(actions, action_checks)
    result: GraphActionRequestResult | None = None
    for index, action in enumerate(actions):
        engine_diag(
            "input:classified",
            action=action.verb,
            index=index + 1,
            total=len(actions),
        )
        result = await _run_classified_action(
            client,
            repo,
            runtime,
            player_input,
            action,
            check_hint_at(action_checks, index),
            scenario_repo=scenario_repo,
        )
        runtime = result.runtime
        if result.status != "executed":
            return result

    if result is None:
        raise GraphInputError("graph input requires at least one action")
    return result


async def _run_classified_actions_stream(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    actions: Sequence[Action],
    action_checks: Sequence[ActionCheckHint],
    player_input: str,
    *,
    scenario_repo: ScenarioRepo | None = None,
) -> AsyncIterator[dict[str, object]]:
    actions, action_checks = normalize_classified_action_sequence(actions, action_checks)
    result: GraphActionRequestResult | None = None
    emitted_result = False
    for index, action in enumerate(actions):
        engine_diag(
            "input:classified",
            action=action.verb,
            index=index + 1,
            total=len(actions),
        )
        async for event in _run_classified_action_stream(
            client,
            repo,
            runtime,
            player_input,
            action,
            check_hint_at(action_checks, index),
            scenario_repo=scenario_repo,
        ):
            if event["type"] == "final":
                result = _event_result(event)
            elif event["type"] == "result":
                if not emitted_result:
                    yield event
                    emitted_result = True
            else:
                yield event

        if result is None:
            raise GraphInputError("graph input requires at least one action")
        runtime = result.runtime
        if result.status != "executed":
            yield {"type": "final", "result": result}
            return

    if result is None:
        raise GraphInputError("graph input requires at least one action")
    yield {"type": "final", "result": result}


async def _run_classified_action(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
    check_hint: ActionCheckHint | None,
    *,
    scenario_repo: ScenarioRepo | None = None,
) -> GraphActionRequestResult:
    action = _with_implicit_speak_target(runtime, action)
    if _should_start_check_roll(
        runtime,
        action,
        check_hint,
        player_input=player_input,
    ):
        from ..roll import start_graph_roll

        return await start_graph_roll(
            repo,
            runtime.progress.game_id,
            action,
            reason=check_hint.reason if check_hint is not None else None,
            player_input=player_input,
            scenario_repo=scenario_repo,
        )
    if (
        (action.verb in {"speak", "pass", "perceive"} or _is_open_generated_move(action))
        and runtime.progress.graph_combat_state is None
    ):
        return await run_graph_narrative_input(
            client,
            repo,
            runtime,
            player_input,
            action,
        )
    try:
        return await run_graph_action_request(
            repo,
            runtime.progress.game_id,
            action,
            llm=client,
            player_input=player_input,
            scenario_repo=scenario_repo,
        )
    except GraphActionTurnError as exc:
        return await run_graph_rejected_input(
            client,
            repo,
            runtime,
            player_input,
            action,
            str(exc),
        )


async def _run_classified_action_stream(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
    check_hint: ActionCheckHint | None,
    *,
    scenario_repo: ScenarioRepo | None = None,
) -> AsyncIterator[dict[str, object]]:
    action = _with_implicit_speak_target(runtime, action)
    if _should_start_check_roll(
        runtime,
        action,
        check_hint,
        player_input=player_input,
    ):
        async for event in run_graph_preroll_stream(
            client,
            repo,
            runtime.progress.game_id,
            action,
            player_input=player_input,
            reason=check_hint.reason if check_hint is not None else None,
            scenario_repo=scenario_repo,
        ):
            yield event
        return
    if (
        (action.verb in {"speak", "pass", "perceive"} or _is_open_generated_move(action))
        and runtime.progress.graph_combat_state is None
    ):
        async for event in run_graph_narrative_input_stream(
            client,
            repo,
            runtime,
            player_input,
            action,
        ):
            yield event
        return
    try:
        async for event in run_graph_action_request_stream(
            repo,
            runtime.progress.game_id,
            action,
            llm=client,
            player_input=player_input,
            scenario_repo=scenario_repo,
        ):
            yield event
    except GraphActionTurnError as exc:
        async for event in run_graph_rejected_input_stream(
            client,
            repo,
            runtime,
            player_input,
            action,
            str(exc),
        ):
            yield event


def _event_result(event: dict[str, object]) -> GraphActionRequestResult:
    result = event.get("result")
    if not isinstance(result, GraphActionRequestResult):
        raise GraphInputError("graph input stream requires result events")
    return result


def _should_start_check_roll(
    runtime: GameRuntimeState,
    action: Action,
    check_hint: ActionCheckHint | None,
    *,
    player_input: str | None = None,
) -> bool:
    return should_start_graph_roll(
        runtime,
        action,
        check_required=check_hint is not None and check_hint.required,
        player_input=player_input,
    )


def _raise_if_pending_input_blocked(runtime: GameRuntimeState) -> None:
    if runtime.progress.pending_confirmation is not None:
        raise GraphConfirmationActive(
            "a pending_confirmation is already active; call graph confirm instead"
        )
    if runtime.progress.pending_roll is not None:
        raise GraphConfirmationActive(
            "a pending_roll is already active; call graph roll instead"
        )

async def _append_player_input_log(
    repo: GraphRepo,
    runtime: GameRuntimeState,
    player_input: str,
) -> GameRuntimeState:
    entry = PlayerLogEntry(
        id=runtime.progress.next_log_id,
        kind="player",
        text=player_input,
    )
    progress = runtime.progress.model_copy(update={"next_log_id": entry.id + 1})
    next_runtime = runtime.model_copy(
        update={
            "progress": progress,
            "log_entries": [*runtime.log_entries, entry],
        }
    )
    await repo.append_log_entries(runtime.progress.game_id, [entry])
    await repo.save_progress(progress)
    return next_runtime

def _is_open_generated_move(action: Action) -> bool:
    return action.verb == "move" and first_ref(action.to) is None
