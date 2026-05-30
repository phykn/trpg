from collections.abc import AsyncIterator

from src.db.repo import GraphRepo
from src.game.domain.action import Action
from src.llm.client import LLMClient
from src.llm.diag import engine_diag
from src.locale.render import render
from src.wire.graph.to_front import graph_to_front_state

from ...env import env_float
from ...narration.input import (
    generate_graph_input_narration,
    generate_graph_input_rejection_narration,
    stream_graph_input_narration,
    stream_graph_input_rejection_narration,
)
from ...narration.result import (
    GraphNarrationResult,
    VisibleNarrationStream,
    gm_log_entry_from_narration,
    parse_graph_narration_answer,
    persist_graph_narration_result,
)
from ...narration.safety import guard_speak_narration_player_quote
from ...narration.suggestions import next_turn_suggestions
from ...request_result import GraphActionRequestResult, rejected_result
from ...state import GameRuntimeState
from ..generated_input import apply_generated_story_after_action
from .targets import (
    action_target as _action_target,
    node_name as _node_name,
    resolve_narrative_subject as _resolve_narrative_subject,
)


def _input_narration_timeout_s(default: float = 120.0) -> float:
    return env_float("LLM_TIMEOUT_S", default)


async def run_graph_rejected_input(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
    rejection_reason: str,
) -> GraphActionRequestResult:
    engine_diag("input:action_rejected", action=action.verb, reason=rejection_reason)
    public_reason = _public_action_rejection_reason(runtime, rejection_reason)
    return await run_graph_rejected_reason_input(
        client,
        repo,
        runtime,
        player_input,
        action,
        public_reason,
    )


async def run_graph_refused_input(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    player_input: str,
    public_reason: str,
    *,
    target: str | None = None,
) -> GraphActionRequestResult:
    action = Action(verb="pass", to=target)
    engine_diag("input:refused", reason=public_reason)
    return await run_graph_rejected_reason_input(
        client,
        repo,
        runtime,
        player_input,
        action,
        public_reason,
    )


async def run_graph_rejected_reason_input(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
    public_reason: str,
) -> GraphActionRequestResult:
    narration_result = await generate_graph_input_rejection_narration(
        client,
        runtime,
        player_input,
        action,
        public_reason,
        timeout_s=_input_narration_timeout_s(),
    )
    text = narration_result.narration or public_reason
    narration_result = narration_result.model_copy(update={"narration": text})
    return await _persist_graph_rejected_input(
        repo,
        runtime,
        player_input,
        action,
        narration_result,
    )


async def run_graph_rejected_input_stream(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
    rejection_reason: str,
) -> AsyncIterator[dict[str, object]]:
    engine_diag("input:action_rejected", action=action.verb, reason=rejection_reason)
    public_reason = _public_action_rejection_reason(runtime, rejection_reason)
    async for event in run_graph_rejected_reason_input_stream(
        client,
        repo,
        runtime,
        player_input,
        action,
        public_reason,
    ):
        yield event


async def run_graph_refused_input_stream(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    player_input: str,
    public_reason: str,
    *,
    target: str | None = None,
) -> AsyncIterator[dict[str, object]]:
    action = Action(verb="pass", to=target)
    engine_diag("input:refused", reason=public_reason)
    async for event in run_graph_rejected_reason_input_stream(
        client,
        repo,
        runtime,
        player_input,
        action,
        public_reason,
    ):
        yield event


async def run_graph_rejected_reason_input_stream(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
    public_reason: str,
) -> AsyncIterator[dict[str, object]]:
    yield {"type": "result", "result": _neutral_stream_result(runtime)}
    stream = VisibleNarrationStream()
    async for chunk in stream_graph_input_rejection_narration(
        client,
        runtime,
        player_input,
        action,
        public_reason,
        timeout_s=_input_narration_timeout_s(),
    ):
        for visible in stream.push(chunk):
            yield {"type": "narration_delta", "text": visible}
    for visible in stream.finish():
        yield {"type": "narration_delta", "text": visible}

    narration_result = parse_graph_narration_answer(stream.answer())
    text = narration_result.narration or public_reason
    narration_result = narration_result.model_copy(update={"narration": text})
    result = await _persist_graph_rejected_input(
        repo,
        runtime,
        player_input,
        action,
        narration_result,
    )
    yield {"type": "final", "result": result}


async def _persist_graph_rejected_input(
    repo: GraphRepo,
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
    narration_result: GraphNarrationResult,
) -> GraphActionRequestResult:
    entry = gm_log_entry_from_narration(
        runtime.progress.next_log_id,
        narration_result,
    )
    progress = runtime.progress.model_copy(
        update={
            "turn_count": runtime.progress.turn_count + 1,
            "next_log_id": entry.id + 1,
        }
    )
    next_runtime = runtime.model_copy(
        update={
            "progress": progress,
            "log_entries": [*runtime.log_entries, entry],
        }
    )
    await repo.append_log_entries(runtime.progress.game_id, [entry])
    await repo.save_progress(progress)
    next_runtime = await persist_graph_narration_result(
        repo,
        next_runtime,
        narration_result,
        player_input=player_input,
        target=_action_target(action),
    )
    engine_diag("input:done", status="rejected", action=action.verb)
    return rejected_result(
        next_runtime,
        graph_to_front_state(next_runtime),
        suggestions=next_turn_suggestions(next_runtime, narration_result.suggestions),
    )


async def run_graph_narrative_input(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
) -> GraphActionRequestResult:
    subject_id = _resolve_narrative_subject(runtime, action)
    narration_result = await generate_graph_input_narration(
        client,
        runtime,
        player_input,
        action,
        subject_id,
        timeout_s=_input_narration_timeout_s(),
    )
    narration_result = _finalize_input_narration(
        runtime,
        action,
        subject_id,
        narration_result,
        player_input,
    )

    return await _finish_graph_narrative_input(
        client,
        repo,
        runtime,
        action,
        subject_id,
        narration_result,
        player_input=player_input,
    )


async def run_graph_narrative_input_stream(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
) -> AsyncIterator[dict[str, object]]:
    subject_id = _resolve_narrative_subject(runtime, action)
    yield {"type": "result", "result": _neutral_stream_result(runtime)}
    stream = VisibleNarrationStream()
    async for chunk in stream_graph_input_narration(
        client,
        runtime,
        player_input,
        action,
        subject_id,
        timeout_s=_input_narration_timeout_s(),
    ):
        for visible in stream.push(chunk):
            yield {"type": "narration_delta", "text": visible}
    for visible in stream.finish():
        yield {"type": "narration_delta", "text": visible}

    narration_result = parse_graph_narration_answer(stream.answer())
    narration_result = _finalize_input_narration(
        runtime,
        action,
        subject_id,
        narration_result,
        player_input,
    )

    result = await _finish_graph_narrative_input(
        client,
        repo,
        runtime,
        action,
        subject_id,
        narration_result,
        player_input=player_input,
    )
    yield {"type": "final", "result": result}


def _finalize_input_narration(
    runtime: GameRuntimeState,
    action: Action,
    subject_id: str | None,
    narration_result: GraphNarrationResult,
    player_input: str,
) -> GraphNarrationResult:
    if not narration_result.narration:
        narration_result = GraphNarrationResult(
            narration=_fallback_input_narration(runtime, subject_id)
        )
    return guard_speak_narration_player_quote(
        runtime,
        action,
        subject_id,
        narration_result,
        player_input,
    )


def _neutral_stream_result(runtime: GameRuntimeState) -> GraphActionRequestResult:
    return GraphActionRequestResult(
        runtime=runtime,
        status="executed",
        outcome="neutral",
        front_state=graph_to_front_state(runtime),
    )


async def _finish_graph_narrative_input(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    action: Action,
    subject_id: str | None,
    narration_result: GraphNarrationResult,
    *,
    player_input: str,
) -> GraphActionRequestResult:
    entry = gm_log_entry_from_narration(
        runtime.progress.next_log_id,
        narration_result,
    )
    progress = runtime.progress.model_copy(
        update={
            "turn_count": runtime.progress.turn_count + 1,
            "next_log_id": entry.id + 1,
            "active_subject_id": subject_id or runtime.progress.active_subject_id,
        }
    )
    next_runtime = runtime.model_copy(
        update={
            "progress": progress,
            "log_entries": [*runtime.log_entries, entry],
        }
    )
    await repo.append_log_entries(runtime.progress.game_id, [entry])
    await repo.save_progress(progress)
    next_runtime = await persist_graph_narration_result(
        repo,
        next_runtime,
        narration_result,
        player_input=player_input,
        target=subject_id,
    )
    engine_diag("input:done", status="executed", action=action.verb)
    result = GraphActionRequestResult(
        runtime=next_runtime,
        status="executed",
        front_state=graph_to_front_state(next_runtime),
        suggestions=next_turn_suggestions(next_runtime, narration_result.suggestions),
    )
    if action.verb not in {"speak", "perceive", "move"}:
        return result
    return await apply_generated_story_after_action(
        client=client,
        repo=repo,
        result=result,
        contract=next_runtime.story_contract,
        player_input=player_input,
        action=action,
        accepted_narration=narration_result.narration,
    )


def _fallback_input_narration(runtime: GameRuntimeState, subject_id: str | None) -> str:
    subject = runtime.graph.nodes.get(subject_id or "")
    if subject is not None:
        return render(
            "runtime.input.dialogue_quiet",
            runtime.progress.locale,
            target=_node_name(runtime, subject),
        )
    return render("runtime.input.quiet", runtime.progress.locale)


def _public_action_rejection_reason(runtime: GameRuntimeState, reason: str) -> str:
    text = reason.lower()
    locale = runtime.progress.locale
    phrase_keys = (
        ("protected target cannot be attacked", "log.error.protected_target"),
        ("hp already full", "log.error.hp_full"),
        ("mp already full", "log.error.mp_full"),
        ("item is not carried", "log.error.item_not_in_inventory"),
        ("missing item", "log.error.unknown_item"),
        ("item is not consumable", "log.error.not_consumable"),
        ("merchant does not have enough gold", "log.error.npc_not_enough_gold"),
        ("source mismatch", "log.error.trade_item_unavailable"),
        ("player does not have enough gold", "log.error.not_enough_gold"),
        ("not enough gold", "log.error.not_enough_gold"),
        ("affinity", "log.error.affinity_too_low"),
        ("equipped item", "log.error.cant_sell_equipped"),
        ("max level", "log.error.max_level"),
        ("not enough experience", "log.error.not_enough_xp"),
    )
    for phrase, key in phrase_keys:
        if phrase in text:
            return render(key, locale)
    return render("log.error.generic_block", locale)
