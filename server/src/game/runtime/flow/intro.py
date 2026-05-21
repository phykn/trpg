from collections.abc import AsyncIterator

from src.db.repo import GraphRepo
from src.game.domain.content import node_label, node_text
from src.game.domain.graph.query import location_of
from src.game.domain.memory import GMLogEntry
from src.locale.render import render

from ..state import GameRuntimeState


async def run_graph_initial_narration(
    repo: GraphRepo,
    runtime: GameRuntimeState,
) -> GameRuntimeState:
    if _already_has_gm_log(runtime) or runtime.progress.turn_count != 0:
        return runtime
    return await _append_intro_entry(repo, runtime, _initial_intro_text(runtime))


async def run_graph_initial_narration_stream(
    repo: GraphRepo,
    runtime: GameRuntimeState,
) -> AsyncIterator[dict[str, object]]:
    if _already_has_gm_log(runtime) or runtime.progress.turn_count != 0:
        yield {"type": "final", "runtime": runtime}
        return

    text = _initial_intro_text(runtime)
    if text:
        yield {"type": "narration_delta", "text": text}
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


def _initial_intro_text(runtime: GameRuntimeState) -> str:
    if runtime.progress.intro_text:
        return _clean_intro_text(runtime.progress.intro_text)
    return _fallback_intro_text(runtime)


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


def _already_has_gm_log(runtime: GameRuntimeState) -> bool:
    return any(entry.kind == "gm" for entry in runtime.log_entries)


def _clean_intro_text(text: str) -> str:
    return text
