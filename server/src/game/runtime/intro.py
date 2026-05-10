from __future__ import annotations

from src.db.repo import GraphRepo
from src.game.domain.graph import GraphNode
from src.game.domain.graph_query import characters_at, edges_from, location_of
from src.game.domain.memory import GMLogEntry
from src.llm.client import LLMClient

from .state import GameRuntimeState

_MAX_INTRO_CHARS = 240


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
    graph = runtime.graph
    place_id = location_of(graph, runtime.progress.player_id)
    if place_id is None:
        return ""
    place = graph.nodes.get(place_id)
    if place is None or place.type != "location":
        return ""
    description = _description(place)
    if description == "없음":
        return _clean_intro_text(f"당신은 {_name(place)}에 도착합니다.")
    return _clean_intro_text(f"당신은 {_name(place)}에 도착합니다. {description}")


async def _generate_intro_text(llm: LLMClient, runtime: GameRuntimeState) -> str:
    prompt = _intro_user_prompt(runtime)
    if not prompt:
        return ""
    result = await llm.chat(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        think=False,
        agent="graph_intro",
        temperature=0.2,
    )
    answer = result.get("answer")
    if not isinstance(answer, str):
        return ""
    return _clean_intro_text(answer)


def _intro_user_prompt(runtime: GameRuntimeState) -> str:
    graph = runtime.graph
    player_id = runtime.progress.player_id
    place_id = location_of(graph, player_id)
    if place_id is None:
        return ""
    place = graph.nodes.get(place_id)
    player = graph.nodes.get(player_id)
    if place is None or place.type != "location" or player is None:
        return ""

    visible_targets = [
        _name(graph.nodes[target_id])
        for target_id in characters_at(graph, place_id)
        if target_id != player_id and target_id in graph.nodes
    ]
    exits = [
        _name(target)
        for edge in edges_from(graph, place_id, "connects_to")
        if (target := graph.nodes.get(edge.to_node_id)) is not None
        and target.type == "location"
    ]
    return "\n".join(
        [
            f"플레이어: {_name(player)}",
            f"장소: {_name(place)}",
            f"장소 설명: {_description(place)}",
            f"보이는 대상: {_join_or_none(visible_targets)}",
            f"나갈 수 있는 곳: {_join_or_none(exits)}",
            "위 사실만 사용해 이 장소에 처음 도착한 느낌을 묘사하십시오.",
        ]
    )


def _already_has_gm_log(runtime: GameRuntimeState) -> bool:
    return any(entry.kind == "gm" for entry in runtime.log_entries)


def _clean_intro_text(text: str) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= _MAX_INTRO_CHARS:
        return cleaned
    return cleaned[:_MAX_INTRO_CHARS].rstrip()


def _name(node: GraphNode) -> str:
    name = node.properties.get("name")
    if isinstance(name, str) and name:
        return name
    title = node.properties.get("title")
    if isinstance(title, str) and title:
        return title
    return node.id


def _description(node: GraphNode) -> str:
    description = node.properties.get("description")
    return description if isinstance(description, str) and description else "없음"


def _join_or_none(values: list[str]) -> str:
    return ", ".join(values) if values else "없음"


_SYSTEM_PROMPT = """당신은 온톨로지 기반 TRPG의 첫 장소 소개만 씁니다.
규칙:
- 한국어로 씁니다.
- 2인칭 존댓말 합니다체를 사용하고 플레이어는 '당신'이라고 부릅니다.
- 1~2문장으로 씁니다.
- 제공된 장소, 대상, 출구만 사용합니다.
- 새 인물, 몬스터, 아이템, 퀘스트, 보상, 전투, 숫자를 만들지 않습니다.
- 그래프 사실을 바꾸거나 행동 결과를 말하지 않습니다."""
