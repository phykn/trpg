from __future__ import annotations

import secrets
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from src.db.repo import GraphRepo
from src.game.domain.action import Action
from src.game.domain.graph import Graph, GraphNode
from src.game.domain.graph_character import can_character_fight
from src.game.domain.graph_query import location_of
from src.llm.client import LLMClient
from src.locale.particles import eul_reul
from src.wire.graph_to_front import GraphFrontStatePayload, graph_to_front_state

from .dispatch import (
    GraphActionDispatchResult,
)
from .load import load_runtime_state
from .state import GameRuntimeState
from .turn import GraphActionTurnError, run_graph_action_turn, run_graph_action_turn_from_runtime


Decision = Literal["confirm", "cancel"]
GraphRequestStatus = Literal[
    "executed",
    "confirmation_required",
    "roll_required",
    "cancelled",
    "answered",
]


class GraphConfirmationError(ValueError):
    pass


class GraphConfirmationActive(GraphConfirmationError):
    pass


class GraphConfirmationExpected(GraphConfirmationError):
    pass


class GraphActionRequestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime: GameRuntimeState
    status: GraphRequestStatus
    front_state: GraphFrontStatePayload
    pending_confirmation: dict[str, Any] | None = None
    pending_roll: dict[str, Any] | None = None
    dispatch: GraphActionDispatchResult | None = None
    message: str | None = None


async def run_graph_action_request(
    repo: GraphRepo,
    game_id: str,
    action: Action,
    *,
    llm: LLMClient | None = None,
) -> GraphActionRequestResult:
    runtime = await load_runtime_state(repo, game_id)
    if runtime.progress.pending_confirmation is not None:
        raise GraphConfirmationActive(
            "a pending_confirmation is already active; call graph confirm instead"
        )
    if runtime.progress.pending_roll is not None:
        raise GraphConfirmationActive(
            "a pending_roll is already active; call graph roll instead"
        )

    if action.verb == "perceive":
        from .roll import start_graph_roll

        return await start_graph_roll(repo, game_id, action)

    if action.verb == "query":
        from .query import answer_graph_query

        return GraphActionRequestResult(
            runtime=runtime,
            status="answered",
            front_state=graph_to_front_state(runtime),
            message=answer_graph_query(runtime, action),
        )

    pending = build_graph_action_confirmation(runtime, action)
    if pending is None:
        result = await run_graph_action_turn(repo, game_id, action, llm=llm)
        return GraphActionRequestResult(
            runtime=result.runtime,
            status="executed",
            front_state=result.front_state,
            dispatch=result.dispatch,
        )

    next_progress = runtime.progress.model_copy(
        update={"pending_confirmation": pending}
    )
    next_runtime = runtime.model_copy(update={"progress": next_progress})
    await repo.save_progress(next_progress)
    return GraphActionRequestResult(
        runtime=next_runtime,
        status="confirmation_required",
        front_state=graph_to_front_state(next_runtime),
        pending_confirmation=pending,
    )


async def run_graph_confirm(
    repo: GraphRepo,
    game_id: str,
    confirmation_id: str,
    decision: Decision,
    *,
    llm: LLMClient | None = None,
) -> GraphActionRequestResult:
    runtime = await load_runtime_state(repo, game_id)
    pending = runtime.progress.pending_confirmation
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
        return GraphActionRequestResult(
            runtime=cleared_runtime,
            status="cancelled",
            front_state=graph_to_front_state(cleared_runtime),
        )

    action = _pending_action(pending)
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

    return GraphActionRequestResult(
        runtime=result.runtime,
        status="executed",
        front_state=result.front_state,
        dispatch=result.dispatch,
    )


def build_graph_action_confirmation(
    runtime: GameRuntimeState,
    action: Action,
) -> dict[str, Any] | None:
    if runtime.progress.graph_combat_state is None and action.verb in (
        "attack",
        "cast",
    ):
        return _build_attack_start_confirmation(runtime, action)

    if action.verb == "transfer" and action.how in ("accept", "abandon"):
        return _build_quest_confirmation(runtime.graph, action)

    return None


def _build_attack_start_confirmation(
    runtime: GameRuntimeState,
    action: Action,
) -> dict[str, Any] | None:
    target_id = _attack_target_id(runtime.graph, runtime.progress.player_id, action)
    if target_id is None:
        return None

    target = runtime.graph.nodes[target_id]
    target_label = _label(target)
    return _pending(
        kind="attack_start",
        title="공격하시겠습니까?",
        body=f"{target_label}{eul_reul(target_label)} 공격해 전투를 시작합니다.",
        confirm_label="공격",
        target_label=target_label,
        action=_normalize_attack_action(action, target_id),
    )


def _build_quest_confirmation(
    graph: Graph,
    action: Action,
) -> dict[str, Any] | None:
    quest_id = _single(action.what) or _single(action.to)
    if quest_id is None:
        return None
    quest = graph.nodes.get(quest_id)
    if quest is None or quest.type != "quest":
        return None

    quest_label = _title(quest)
    if action.how == "accept":
        return _pending(
            kind="quest_accept",
            title="퀘스트를 시작하시겠습니까?",
            body=f"{quest_label} 퀘스트를 시작합니다.",
            confirm_label="시작",
            target_label=quest_label,
            action=action,
        )

    return _pending(
        kind="quest_abandon",
        title="퀘스트를 포기하시겠습니까?",
        body=f"{quest_label} 퀘스트를 포기합니다.",
        confirm_label="포기",
        target_label=quest_label,
        action=action,
    )


def _pending(
    *,
    kind: str,
    title: str,
    body: str,
    confirm_label: str,
    target_label: str,
    action: Action,
) -> dict[str, Any]:
    return {
        "id": f"confirm_{secrets.token_hex(4)}",
        "kind": kind,
        "title": title,
        "body": body,
        "confirm_label": confirm_label,
        "cancel_label": "취소",
        "target_label": target_label,
        "payload": {
            "kind": "graph_action",
            "action": action.model_dump(mode="json", by_alias=True),
        },
    }


def _pending_action(pending: dict[str, Any]) -> Action:
    payload = pending.get("payload")
    if not isinstance(payload, dict) or payload.get("kind") != "graph_action":
        raise GraphConfirmationExpected("pending graph action missing")
    action_data = payload.get("action")
    if not isinstance(action_data, dict):
        raise GraphConfirmationExpected("pending action missing")
    return Action.model_validate(action_data)


def _attack_target_id(
    graph: Graph,
    player_id: str,
    action: Action,
) -> str | None:
    if action.verb == "attack":
        candidates = _list(action.what)
    elif action.verb == "cast":
        candidates = _list(action.to)
    else:
        return None
    for target_id in candidates:
        if _can_target_start_combat(graph, player_id, target_id):
            return target_id
    return None


def _normalize_attack_action(action: Action, target_id: str) -> Action:
    if action.verb == "attack":
        return action.model_copy(update={"what": [target_id]})
    if action.verb == "cast":
        return action.model_copy(update={"to": target_id})
    return action


def _can_target_start_combat(
    graph: Graph,
    player_id: str,
    target_id: str,
) -> bool:
    player_location = location_of(graph, player_id)
    target_location = location_of(graph, target_id)
    target = graph.nodes.get(target_id)
    return (
        target is not None
        and target.type == "character"
        and target_id != player_id
        and can_character_fight(target)
        and player_location is not None
        and target_location == player_location
    )


def _title(node: GraphNode) -> str:
    title = node.properties.get("title")
    if isinstance(title, str) and title:
        return title
    return _label(node)


def _label(node: GraphNode) -> str:
    name = node.properties.get("name")
    return name if isinstance(name, str) and name else node.id


def _single(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value and isinstance(value[0], str):
        return value[0]
    return None


def _list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []

