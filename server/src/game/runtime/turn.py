from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from src.db.repo import GraphRepo
from src.game.domain.action import Action
from src.game.domain.errors import LLMUnavailable
from src.game.domain.graph import GraphNode
from src.game.domain.graph_query import location_of
from src.game.domain.memory import GMLogEntry
from src.game.engines.graph_quest_generation import plan_missing_quest_offer
from src.llm.client import LLMClient
from src.wire.graph_to_front import GraphFrontStatePayload, graph_to_front_state

from .apply import apply_runtime_graph_changes
from .dispatch import (
    GraphActionDispatchError,
    GraphActionDispatchResult,
    dispatch_graph_action,
)
from .cards import build_graph_action_card, build_graph_quest_offer_card
from .load import load_runtime_state
from .state import GameRuntimeState


class GraphActionTurnError(ValueError):
    pass


class GraphActionTurnResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime: GameRuntimeState
    dispatch: GraphActionDispatchResult
    front_state: GraphFrontStatePayload


async def run_graph_action_turn(
    repo: GraphRepo,
    game_id: str,
    action: Action,
    *,
    llm: LLMClient | None = None,
) -> GraphActionTurnResult:
    runtime = await load_runtime_state(repo, game_id)
    return await run_graph_action_turn_from_runtime(
        repo,
        game_id,
        runtime,
        action,
        llm=llm,
    )


async def run_graph_action_turn_from_runtime(
    repo: GraphRepo,
    game_id: str,
    runtime: GameRuntimeState,
    action: Action,
    *,
    llm: LLMClient | None = None,
) -> GraphActionTurnResult:
    try:
        dispatch = dispatch_graph_action(runtime, action)
    except GraphActionDispatchError as exc:
        raise GraphActionTurnError(str(exc)) from exc

    next_runtime = dispatch.runtime
    offer_quest_id: str | None = None
    if next_runtime.progress.graph_combat_state is None:
        offer = plan_missing_quest_offer(
            next_runtime.graph,
            next_runtime.progress.player_id,
        )
        if offer is not None:
            next_runtime = apply_runtime_graph_changes(
                next_runtime,
                offer.changes,
            ).runtime
            offer_quest_id = offer.quest_id
    card = build_graph_action_card(runtime, next_runtime, action, dispatch)
    cards = [card]
    if offer_quest_id is not None:
        cards.append(
            build_graph_quest_offer_card(
                next_runtime,
                offer_quest_id,
                card.id + 1,
            )
        )
    narration = await _build_graph_action_narration(
        llm,
        before=runtime,
        after=next_runtime,
        action=action,
        dispatch=dispatch,
        card_texts=[card.text for card in cards],
    )
    log_entries = [*cards]
    if narration:
        log_entries.append(
            GMLogEntry(
                id=card.id + len(cards),
                kind="gm",
                text=narration,
            )
        )

    next_progress = next_runtime.progress.model_copy(
        update={"next_log_id": card.id + len(log_entries)}
    )
    next_runtime = next_runtime.model_copy(
        update={
            "progress": next_progress,
            "log_entries": [*next_runtime.log_entries, *log_entries],
        }
    )
    await repo.save_graph(game_id, next_runtime.graph)
    await repo.append_log_entries(game_id, log_entries)
    await repo.save_progress(next_runtime.progress)
    return GraphActionTurnResult(
        runtime=next_runtime,
        dispatch=dispatch,
        front_state=graph_to_front_state(next_runtime),
    )


async def _build_graph_action_narration(
    llm: LLMClient | None,
    *,
    before: GameRuntimeState,
    after: GameRuntimeState,
    action: Action,
    dispatch: GraphActionDispatchResult,
    card_texts: list[str],
) -> str:
    if llm is None or not _needs_graph_action_narration(before, after, action, dispatch):
        return ""
    prompt = _narration_user_prompt(before, after, card_texts)
    if not prompt:
        return ""
    try:
        result = await llm.chat(
            [
                {"role": "system", "content": _NARRATION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
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


def _needs_graph_action_narration(
    before: GameRuntimeState,
    after: GameRuntimeState,
    action: Action,
    dispatch: GraphActionDispatchResult,
) -> bool:
    if dispatch.kind == "combat":
        return True
    if dispatch.kind in {"quest_accept", "quest_abandon"}:
        return True
    if action.verb == "move":
        return False
    return before.progress.active_quest_id != after.progress.active_quest_id


def _narration_user_prompt(
    before: GameRuntimeState,
    after: GameRuntimeState,
    card_texts: list[str],
) -> str:
    player = after.graph.nodes.get(after.progress.player_id)
    place_id = location_of(after.graph, after.progress.player_id)
    place = after.graph.nodes.get(place_id or "")
    facts = [
        f"플레이어: {_node_name(player)}",
        f"현재 장소: {_node_name(place)}",
        f"장소 설명: {_node_description(place)}",
        f"처리된 결과: {' / '.join(card_texts)}",
    ]
    if before.progress.graph_combat_state is not None or after.progress.graph_combat_state is not None:
        facts.append("상황: 전투 장면")
    return "\n".join(facts)


def _clean_narration(text: str) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= 220:
        return cleaned
    return cleaned[:220].rstrip()


def _node_name(node: GraphNode | None) -> str:
    if node is None:
        return "없음"
    name = node.properties.get("name")
    if isinstance(name, str) and name:
        return name
    title = node.properties.get("title")
    if isinstance(title, str) and title:
        return title
    return node.id


def _node_description(node: GraphNode | None) -> str:
    if node is None:
        return "없음"
    description = node.properties.get("description")
    return description if isinstance(description, str) and description else "없음"


_NARRATION_SYSTEM_PROMPT = """당신은 온톨로지 기반 TRPG의 짧은 GM 나레이션만 씁니다.
규칙:
- 한국어로 씁니다.
- 2인칭 존댓말 합니다체를 사용하고 플레이어는 '당신'이라고 부릅니다.
- 1~2문장, 최대 220자입니다.
- 제공된 사실만 사용합니다.
- 새 인물, 장소, 몬스터, 아이템, 퀘스트, 보상, 숫자를 만들지 않습니다.
- 행동 결과를 뒤집거나 그래프 상태를 바꾸는 말을 하지 않습니다.
- 시스템 카드 문장을 그대로 반복하지 말고, 장면의 감각과 반응만 덧붙입니다."""
