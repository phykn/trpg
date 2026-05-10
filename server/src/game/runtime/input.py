from __future__ import annotations

import json

from src.db.repo import GraphRepo
from src.game.domain.action import verb_to_action
from src.game.domain.errors import LLMUnavailable
from src.game.domain.graph import GraphNode
from src.game.domain.graph_query import characters_at, location_of
from src.game.domain.memory import GMLogEntry
from src.llm.calls.classify.runner import classify
from src.llm.calls.classify.schema import JudgeInput
from src.llm.client import LLMClient
from src.llm.context.graph_surroundings import build_graph_surroundings
from src.wire.graph_to_front import graph_to_front_state

from .confirmation import GraphActionRequestResult, run_graph_action_request
from .load import load_runtime_state


class GraphInputError(ValueError):
    pass


async def run_graph_input_turn(
    client: LLMClient,
    repo: GraphRepo,
    game_id: str,
    player_input: str,
) -> GraphActionRequestResult:
    runtime = await load_runtime_state(repo, game_id)
    output = await classify(
        client,
        JudgeInput(
            player_input=player_input,
            surroundings=build_graph_surroundings(runtime),
        ),
        locale=runtime.progress.locale,
    )

    if output.refuse is not None:
        raise GraphInputError(output.refuse.reason)
    actions = output.actions or []
    if len(actions) != 1:
        raise GraphInputError("graph input requires exactly one action")

    action = verb_to_action(actions[0])
    if action.verb in {"speak", "perceive", "pass"}:
        return await _run_graph_narrative_input(
            client,
            repo,
            runtime,
            player_input,
            action,
        )

    return await run_graph_action_request(
        repo,
        game_id,
        action,
        llm=client,
    )


async def _run_graph_narrative_input(
    client: LLMClient,
    repo: GraphRepo,
    runtime,
    player_input: str,
    action,
) -> GraphActionRequestResult:
    subject_id = _resolve_narrative_subject(runtime, action)
    text = await _generate_graph_input_narration(
        client,
        runtime,
        player_input,
        action,
        subject_id,
    )
    if not text:
        text = "당신의 행동은 조용히 이어집니다."
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
    return GraphActionRequestResult(
        runtime=next_runtime,
        status="executed",
        front_state=graph_to_front_state(next_runtime),
    )


async def _generate_graph_input_narration(
    client: LLMClient,
    runtime,
    player_input: str,
    action,
    subject_id: str | None,
) -> str:
    surroundings = build_graph_surroundings(runtime)
    subject = runtime.graph.nodes.get(subject_id or "")
    subject_line = (
        f"대화 대상: {subject_id} / {_node_name(subject)}"
        if subject_id is not None
        else "대화 대상: 없음"
    )
    subject_state = (
        "대상 상태: 현재 장소에 있음"
        if subject_id is not None and _is_at_player_location(runtime, subject_id)
        else "대상 상태: 지정되지 않음"
    )
    try:
        result = await client.chat(
            [
                {"role": "system", "content": _NARRATIVE_INPUT_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": "\n".join(
                        [
                            f"플레이어 입력: {player_input}",
                            f"분류된 행동: {action.verb}",
                            subject_line,
                            subject_state,
                            f"현재 상황: {json.dumps(surroundings, ensure_ascii=False)}",
                        ]
                    ),
                },
            ],
            think=False,
            agent="graph_narrate",
            temperature=0.2,
        )
    except (LLMUnavailable, OSError, TimeoutError):
        return ""
    answer = result.get("answer")
    if not isinstance(answer, str):
        return ""
    return _clean_narration(answer)


def _resolve_narrative_subject(runtime, action) -> str | None:
    target_id = _single(action.what) or _single(action.to)
    if isinstance(target_id, str) and _is_at_player_location(runtime, target_id):
        return target_id
    if action.verb != "speak":
        return None
    location_id = location_of(runtime.graph, runtime.progress.player_id)
    if location_id is None:
        return None
    for character_id in characters_at(runtime.graph, location_id):
        if character_id == runtime.progress.player_id:
            continue
        node = runtime.graph.nodes.get(character_id)
        if node is None or node.type != "character":
            continue
        if _node_hp(node) > 0:
            return character_id
    return None


def _is_at_player_location(runtime, node_id: str) -> bool:
    player_location = location_of(runtime.graph, runtime.progress.player_id)
    return player_location is not None and location_of(runtime.graph, node_id) == player_location


def _node_name(node: GraphNode | None) -> str:
    if node is None:
        return "없음"
    name = node.properties.get("name")
    return name if isinstance(name, str) and name else node.id


def _node_hp(node: GraphNode) -> int:
    hp = node.properties.get("hp")
    return hp if isinstance(hp, int) else 0


def _single(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value and isinstance(value[0], str):
        return value[0]
    return None


def _clean_narration(text: str) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= 220:
        return cleaned
    return cleaned[:220].rstrip()


_NARRATIVE_INPUT_SYSTEM_PROMPT = """당신은 온톨로지 기반 TRPG의 짧은 GM 나레이션만 씁니다.
규칙:
- 한국어로 씁니다.
- 2인칭 존댓말 합니다체를 사용하고 플레이어는 '당신'이라고 부릅니다.
- 1~2문장, 최대 220자입니다.
- 제공된 현재 상황과 플레이어 입력만 사용합니다.
- 분류된 행동이 speak이고 대화 대상이 있으면 NPC의 짧은 반응이나 대사를 포함합니다.
- 새 인물, 장소, 몬스터, 아이템, 퀘스트, 보상, 숫자를 만들지 않습니다.
- 그래프 상태를 바꾸거나 확정되지 않은 보상을 말하지 않습니다."""
