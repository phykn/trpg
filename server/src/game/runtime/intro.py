import json
from collections.abc import AsyncIterator

from openai import APIConnectionError, InternalServerError, RateLimitError

from src.db.repo import GraphRepo
from src.game.domain.content import node_label, node_text
from src.game.domain.errors import LLMUnavailable
from src.game.domain.graph_query import location_of
from src.game.domain.memory import GMLogEntry
from src.llm.calls._runner import get_prompt
from src.llm.client import LLMClient
from src.llm.diag import llm_diag
from src.locale.render import render

from .narration_context import build_intro_narration_payload
from .narration_result import VisibleNarrationStream
from .state import GameRuntimeState


async def run_graph_initial_narration(
    llm: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
) -> GameRuntimeState:
    if _already_has_gm_log(runtime) or runtime.progress.turn_count != 0:
        return runtime

    text = await _generate_intro_text(llm, runtime)
    if not text:
        text = _fallback_intro_text(runtime)
    return await _append_intro_entry(repo, runtime, text)


async def run_graph_initial_narration_stream(
    llm: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
) -> AsyncIterator[dict[str, object]]:
    if _already_has_gm_log(runtime) or runtime.progress.turn_count != 0:
        yield {"type": "final", "runtime": runtime}
        return

    stream = VisibleNarrationStream()
    async for chunk in _stream_intro_text(llm, runtime):
        for visible in stream.push(chunk):
            yield {"type": "delta", "text": visible}
    for visible in stream.finish():
        yield {"type": "delta", "text": visible}

    text = _clean_intro_text(stream.answer())
    if not text:
        text = _fallback_intro_text(runtime)
    yield {"type": "final", "runtime": await _append_intro_entry(repo, runtime, text)}


async def run_graph_initial_fallback_narration(
    repo: GraphRepo,
    runtime: GameRuntimeState,
) -> GameRuntimeState:
    if _already_has_gm_log(runtime) or runtime.progress.turn_count != 0:
        return runtime
    return await _append_intro_entry(repo, runtime, _fallback_intro_text(runtime))


async def _append_intro_entry(
    repo: GraphRepo,
    runtime: GameRuntimeState,
    text: str,
) -> GameRuntimeState:
    if not text:
        return runtime
    entry = GMLogEntry(id=runtime.progress.next_log_id, kind="gm", text=text)
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


def _fallback_intro_text(runtime: GameRuntimeState) -> str:
    graph = runtime.graph_index
    place_id = location_of(graph, runtime.progress.player_id)
    if place_id is None:
        return ""
    place = graph.nodes.get(place_id)
    if place is None or place.type != "location":
        return ""
    description = node_text(runtime.content, place, "description")
    if description is None:
        return _clean_intro_text(
            render(
                "runtime.intro.arrive",
                runtime.progress.locale,
                place=node_label(runtime.content, place),
            )
        )
    return _clean_intro_text(
        render(
            "runtime.intro.arrive_with_description",
            runtime.progress.locale,
            place=node_label(runtime.content, place),
            description=description,
        )
    )


async def _generate_intro_text(llm: LLMClient, runtime: GameRuntimeState) -> str:
    prompt = _intro_user_prompt(runtime)
    if not prompt:
        return ""
    llm_diag("llm:call", agent="graph_intro")
    try:
        result = await llm.chat(
            [
                {
                    "role": "system",
                    "content": get_prompt("graph_intro", runtime.progress.locale),
                },
                {"role": "user", "content": prompt},
            ],
            think=False,
            agent="graph_intro",
            temperature=0.2,
        )
    except (
        LLMUnavailable,
        OSError,
        TimeoutError,
        InternalServerError,
        APIConnectionError,
        RateLimitError,
    ) as exc:
        llm_diag("llm:fail", agent="graph_intro", err=type(exc).__name__)
        raise LLMUnavailable(str(exc)) from exc
    llm_diag("llm:done", agent="graph_intro")
    answer = result.get("answer")
    if not isinstance(answer, str):
        return ""
    return _clean_intro_text(answer)


async def _stream_intro_text(
    llm: LLMClient,
    runtime: GameRuntimeState,
) -> AsyncIterator[str]:
    prompt = _intro_user_prompt(runtime)
    if not prompt:
        return
    llm_diag("llm:call", agent="graph_intro")
    try:
        async for part in llm.chat_stream(
            [
                {
                    "role": "system",
                    "content": get_prompt("graph_intro", runtime.progress.locale),
                },
                {"role": "user", "content": prompt},
            ],
            think=False,
            agent="graph_intro",
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
        llm_diag("llm:fail", agent="graph_intro", err=type(exc).__name__)
        raise LLMUnavailable(str(exc)) from exc
    llm_diag("llm:done", agent="graph_intro")


def _intro_user_prompt(runtime: GameRuntimeState) -> str:
    payload = build_intro_narration_payload(runtime)
    if payload["place"] is None:
        return ""
    return json.dumps(payload, ensure_ascii=False)


def _already_has_gm_log(runtime: GameRuntimeState) -> bool:
    return any(entry.kind == "gm" for entry in runtime.log_entries)


def _clean_intro_text(text: str) -> str:
    return text
