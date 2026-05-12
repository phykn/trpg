import asyncio
import json
from collections.abc import AsyncIterator, Sequence

from openai import APIConnectionError, InternalServerError, RateLimitError

from src.db.repo import GraphRepo, ScenarioRepo
from src.game.domain.action import Action
from src.game.domain.content import node_label
from src.game.domain.errors import LLMUnavailable
from src.game.domain.graph import GraphNode
from src.game.domain.graph_query import characters_at, location_of
from src.game.domain.memory import GMLogEntry, PlayerLogEntry
from src.game.engines.graph_social_quest import (
    SocialQuestResult,
    plan_social_quest_speak,
)
from src.llm.calls._runner import get_prompt
from src.llm.calls.classify.runner import classify
from src.llm.calls.classify.schema import ClassifyInput
from src.llm.context.classify_view import build_classify_context_view
from src.llm.client import LLMClient
from src.llm.diag import engine_diag, llm_diag, set_diag_context
from src.locale.render import render
from src.wire.graph_to_front import graph_to_front_state

from .apply import apply_runtime_graph_changes
from .confirmation import GraphActionRequestResult, run_graph_action_request
from .load import load_runtime_state
from .narration_context import build_input_narration_payload
from .narration_result import (
    GraphNarrationResult,
    VisibleNarrationStream,
    parse_graph_narration_answer,
    persist_graph_narration_result,
)
from .state import GameRuntimeState


class GraphInputError(ValueError):
    pass


_GRAPH_INPUT_NARRATION_TIMEOUT_SECONDS = 30.0


async def run_graph_input_turn(
    client: LLMClient,
    repo: GraphRepo,
    game_id: str,
    player_input: str,
    scenario_repo: ScenarioRepo | None = None,
) -> GraphActionRequestResult:
    runtime = await load_runtime_state(repo, game_id, scenario_repo)
    set_diag_context(game_id, runtime.progress.turn_count)
    engine_diag("input:start", chars=len(player_input))
    runtime = await _append_player_input_log(repo, runtime, player_input)
    output = await classify(
        client,
        ClassifyInput(
            player_input=player_input,
            context=build_classify_context_view(runtime, player_input),
        ),
        locale=runtime.progress.locale,
    )

    if output.refuse is not None:
        raise GraphInputError(output.refuse.message_hint)
    actions = output.actions or []
    if not actions:
        raise GraphInputError("graph input requires at least one action")

    return await _run_classified_actions(
        client,
        repo,
        runtime,
        actions,
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
    runtime = await load_runtime_state(repo, game_id, scenario_repo)
    set_diag_context(game_id, runtime.progress.turn_count)
    engine_diag("input:start", chars=len(player_input))
    runtime = await _append_player_input_log(repo, runtime, player_input)
    output = await classify(
        client,
        ClassifyInput(
            player_input=player_input,
            context=build_classify_context_view(runtime, player_input),
        ),
        locale=runtime.progress.locale,
    )

    if output.refuse is not None:
        raise GraphInputError(output.refuse.message_hint)
    actions = output.actions or []
    if not actions:
        raise GraphInputError("graph input requires at least one action")

    async for event in _run_classified_actions_stream(
        client,
        repo,
        runtime,
        actions,
        player_input,
        scenario_repo=scenario_repo,
    ):
        yield event


async def _run_classified_actions(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    actions: Sequence[Action],
    player_input: str,
    *,
    scenario_repo: ScenarioRepo | None = None,
) -> GraphActionRequestResult:
    result: GraphActionRequestResult | None = None
    for index, action in enumerate(actions):
        engine_diag(
            "input:classified",
            action=action.verb,
            index=index + 1,
            total=len(actions),
        )
        if action.verb in {"speak", "pass"}:
            result = await _run_graph_narrative_input(
                client,
                repo,
                runtime,
                player_input,
                action,
            )
        else:
            result = await run_graph_action_request(
                repo,
                runtime.progress.game_id,
                action,
                llm=client,
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
    player_input: str,
    *,
    scenario_repo: ScenarioRepo | None = None,
) -> AsyncIterator[dict[str, object]]:
    result: GraphActionRequestResult | None = None
    for index, action in enumerate(actions):
        engine_diag(
            "input:classified",
            action=action.verb,
            index=index + 1,
            total=len(actions),
        )
        if action.verb in {"speak", "pass"}:
            async for event in _run_graph_narrative_input_stream(
                client,
                repo,
                runtime,
                player_input,
                action,
            ):
                if event["type"] == "final":
                    result = event["result"]  # type: ignore[assignment]
                else:
                    yield event
        else:
            result = await run_graph_action_request(
                repo,
                runtime.progress.game_id,
                action,
                llm=client,
                scenario_repo=scenario_repo,
            )

        if result is None:
            raise GraphInputError("graph input requires at least one action")
        runtime = result.runtime
        if result.status != "executed":
            yield {"type": "final", "result": result}
            return

    if result is None:
        raise GraphInputError("graph input requires at least one action")
    yield {"type": "final", "result": result}


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
    progress = runtime.progress.model_copy(
        update={"next_log_id": entry.id + 1}
    )
    next_runtime = runtime.model_copy(
        update={
            "progress": progress,
            "log_entries": [*runtime.log_entries, entry],
        }
    )
    await repo.append_log_entries(runtime.progress.game_id, [entry])
    await repo.save_progress(progress)
    return next_runtime


async def _run_graph_narrative_input(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
) -> GraphActionRequestResult:
    subject_id = _resolve_narrative_subject(runtime, action)
    social_result = _plan_social_quest_speak(runtime, player_input, action, subject_id)
    if social_result is not None:
        next_runtime = await _apply_social_quest_speak_result(
            repo,
            runtime,
            social_result,
        )
        return await _finish_fixed_graph_narrative_input(
            repo,
            next_runtime,
            action,
            subject_id,
            render(social_result.message_key, runtime.progress.locale),
        )

    narration_result = await _generate_graph_input_narration(
        client,
        runtime,
        player_input,
        action,
        subject_id,
    )
    text = narration_result.narration
    if not text:
        text = _fallback_input_narration(runtime, subject_id)
        narration_result = GraphNarrationResult(narration=text)
    entry = GMLogEntry(
        id=runtime.progress.next_log_id,
        kind="gm",
        text=text,
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
        target_id=subject_id,
    )
    engine_diag("input:done", status="executed", action=action.verb)
    return GraphActionRequestResult(
        runtime=next_runtime,
        status="executed",
        front_state=graph_to_front_state(next_runtime),
        suggestions=narration_result.suggestions,
    )


async def _run_graph_narrative_input_stream(
    client: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
) -> AsyncIterator[dict[str, object]]:
    subject_id = _resolve_narrative_subject(runtime, action)
    social_result = _plan_social_quest_speak(runtime, player_input, action, subject_id)
    if social_result is not None:
        next_runtime = await _apply_social_quest_speak_result(
            repo,
            runtime,
            social_result,
        )
        text = render(social_result.message_key, runtime.progress.locale)
        yield {"type": "delta", "text": text}
        result = await _finish_fixed_graph_narrative_input(
            repo,
            next_runtime,
            action,
            subject_id,
            text,
        )
        yield {"type": "final", "result": result}
        return

    stream = VisibleNarrationStream()
    async for chunk in _stream_graph_input_narration(
        client,
        runtime,
        player_input,
        action,
        subject_id,
    ):
        for visible in stream.push(chunk):
            yield {"type": "delta", "text": visible}
    for visible in stream.finish():
        yield {"type": "delta", "text": visible}

    narration_result = parse_graph_narration_answer(stream.answer())
    text = narration_result.narration
    if not text:
        text = _fallback_input_narration(runtime, subject_id)
        narration_result = GraphNarrationResult(narration=text)
    entry = GMLogEntry(
        id=runtime.progress.next_log_id,
        kind="gm",
        text=text,
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
        target_id=subject_id,
    )
    engine_diag("input:done", status="executed", action=action.verb)
    yield {
        "type": "final",
        "result": GraphActionRequestResult(
            runtime=next_runtime,
            status="executed",
            front_state=graph_to_front_state(next_runtime),
            suggestions=narration_result.suggestions,
        ),
    }


def _plan_social_quest_speak(
    runtime: GameRuntimeState,
    player_input: str,
    action: Action,
    subject_id: str | None,
) -> SocialQuestResult | None:
    if action.verb != "speak":
        return None
    return plan_social_quest_speak(
        runtime.graph,
        player_id=runtime.progress.player_id,
        target_id=subject_id,
        how=action.how,
        player_input=player_input,
    )


async def _apply_social_quest_speak_result(
    repo: GraphRepo,
    runtime: GameRuntimeState,
    social_result: SocialQuestResult,
) -> GameRuntimeState:
    if not social_result.changes:
        return runtime
    apply_result = apply_runtime_graph_changes(runtime, social_result.changes)
    await repo.save_graph_changes(
        runtime.progress.game_id,
        apply_result.runtime.graph,
        changed_node_ids=apply_result.changed_node_ids,
        changed_edge_ids=apply_result.changed_edge_ids,
        removed_edge_ids=apply_result.removed_edge_ids,
    )
    return apply_result.runtime


async def _finish_fixed_graph_narrative_input(
    repo: GraphRepo,
    runtime: GameRuntimeState,
    action: Action,
    subject_id: str | None,
    text: str,
) -> GraphActionRequestResult:
    entry = GMLogEntry(
        id=runtime.progress.next_log_id,
        kind="gm",
        text=text,
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
    engine_diag("input:done", status="executed", action=action.verb)
    return GraphActionRequestResult(
        runtime=next_runtime,
        status="executed",
        front_state=graph_to_front_state(next_runtime),
        suggestions=[],
    )


async def _generate_graph_input_narration(
    client: LLMClient,
    runtime,
    player_input: str,
    action,
    subject_id: str | None,
) -> GraphNarrationResult:
    messages = _graph_input_narration_messages(
        runtime,
        player_input,
        action,
        subject_id,
    )
    try:
        llm_diag("llm:call", agent="graph_narrate")
        result = await asyncio.wait_for(
            client.chat(
                messages,
                think=False,
                agent="graph_narrate",
                temperature=0.2,
            ),
            timeout=_GRAPH_INPUT_NARRATION_TIMEOUT_SECONDS,
        )
    except (
        LLMUnavailable,
        OSError,
        TimeoutError,
        InternalServerError,
        APIConnectionError,
        RateLimitError,
    ) as exc:
        llm_diag("llm:fail", agent="graph_narrate", err=type(exc).__name__)
        return GraphNarrationResult()
    llm_diag("llm:done", agent="graph_narrate")
    answer = result.get("answer")
    if not isinstance(answer, str):
        return GraphNarrationResult()
    return parse_graph_narration_answer(
        _clean_narration(answer, recent_texts=_recent_gm_texts(runtime))
    )


async def _stream_graph_input_narration(
    client: LLMClient,
    runtime,
    player_input: str,
    action,
    subject_id: str | None,
) -> AsyncIterator[str]:
    messages = _graph_input_narration_messages(
        runtime,
        player_input,
        action,
        subject_id,
    )
    try:
        llm_diag("llm:call", agent="graph_narrate")
        async with asyncio.timeout(_GRAPH_INPUT_NARRATION_TIMEOUT_SECONDS):
            async for part in client.chat_stream(
                messages,
                think=False,
                agent="graph_narrate",
                temperature=0.2,
            ):
                answer = part.get("answer")
                if isinstance(answer, str) and answer:
                    yield answer
    except (
        LLMUnavailable,
        OSError,
        TimeoutError,
        InternalServerError,
        APIConnectionError,
        RateLimitError,
    ) as exc:
        llm_diag("llm:fail", agent="graph_narrate", err=type(exc).__name__)
        return
    llm_diag("llm:done", agent="graph_narrate")


def _graph_input_narration_messages(
    runtime,
    player_input: str,
    action,
    subject_id: str | None,
) -> list[dict[str, str]]:
    subject = runtime.graph.nodes.get(subject_id or "")
    payload = build_input_narration_payload(
        runtime=runtime,
        player_input=player_input,
        action=action,
        dialogue_target=subject if subject_id is not None else None,
    )
    return [
        {
            "role": "system",
            "content": get_prompt("graph_narrate", runtime.progress.locale),
        },
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False),
        },
    ]


def _resolve_narrative_subject(runtime, action) -> str | None:
    target_id = _single(action.what) or _single(action.to)
    if isinstance(target_id, str) and _is_at_player_location(runtime, target_id):
        return target_id
    if action.verb != "speak":
        return None
    graph = runtime.graph_index
    location_id = location_of(graph, runtime.progress.player_id)
    if location_id is None:
        return None
    for character_id in characters_at(graph, location_id):
        if character_id == runtime.progress.player_id:
            continue
        node = graph.nodes.get(character_id)
        if node is None or node.type != "character":
            continue
        if _node_hp(node) > 0:
            return character_id
    return None


def _is_at_player_location(runtime, node_id: str) -> bool:
    graph = runtime.graph_index
    player_location = location_of(graph, runtime.progress.player_id)
    return (
        player_location is not None and location_of(graph, node_id) == player_location
    )


def _node_name(runtime, node: GraphNode | None) -> str:
    if node is None:
        return render("runtime.none", runtime.progress.locale)
    return node_label(runtime.content, node)


def _node_hp(node: GraphNode) -> int:
    hp = node.properties.get("hp")
    return hp if isinstance(hp, int) else 0


def _fallback_input_narration(runtime: GameRuntimeState, subject_id: str | None) -> str:
    subject = runtime.graph.nodes.get(subject_id or "")
    if subject is not None:
        return render(
            "runtime.input.dialogue_quiet",
            runtime.progress.locale,
            target=_node_name(runtime, subject),
        )
    return render("runtime.input.quiet", runtime.progress.locale)


def _single(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value and isinstance(value[0], str):
        return value[0]
    return None


def _clean_narration(text: str, *, recent_texts=()) -> str:
    return text


def _recent_gm_texts(runtime: GameRuntimeState) -> list[str]:
    return [
        entry.text
        for entry in runtime.log_entries[-4:]
        if getattr(entry, "kind", None) == "gm" and hasattr(entry, "text")
    ]
