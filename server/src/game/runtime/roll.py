from __future__ import annotations

import random
import secrets
from typing import Any

from src.db.repo import GraphRepo
from src.game.domain.action import Action
from src.game.domain.memory import BonusItem, RollLogEntry
from src.game.rules.dc import compute_grade, compute_required_roll
from src.locale.labels import ROLL_DICE_LABEL, stat_label
from src.wire.graph_to_front import graph_to_front_state

from .confirmation import GraphActionRequestResult
from .load import load_runtime_state


class GraphRollError(ValueError):
    pass


class GraphRollExpected(GraphRollError):
    pass


class GraphRollActive(GraphRollError):
    pass


DEFAULT_ROLL_DC = 13


async def start_graph_roll(
    repo: GraphRepo,
    game_id: str,
    action: Action,
) -> GraphActionRequestResult:
    runtime = await load_runtime_state(repo, game_id)
    if runtime.progress.pending_roll is not None:
        raise GraphRollActive("a pending_roll is already active")
    if runtime.progress.pending_confirmation is not None:
        raise GraphRollActive("a pending_confirmation is already active")

    pending = build_pending_roll(runtime.graph.nodes[runtime.progress.player_id].properties, action)
    next_progress = runtime.progress.model_copy(update={"pending_roll": pending})
    next_runtime = runtime.model_copy(update={"progress": next_progress})
    await repo.save_progress(next_progress)
    return GraphActionRequestResult(
        runtime=next_runtime,
        status="roll_required",
        front_state=graph_to_front_state(next_runtime),
        pending_roll=pending,
    )


async def run_graph_roll(
    repo: GraphRepo,
    game_id: str,
    roll_id: str,
    *,
    dice: int | None = None,
) -> GraphActionRequestResult:
    runtime = await load_runtime_state(repo, game_id)
    pending = runtime.progress.pending_roll
    if pending is None:
        raise GraphRollExpected("no pending_roll")
    if pending.get("id") != roll_id:
        raise GraphRollExpected("roll id mismatch")

    required_roll = _int(pending.get("required_roll"), "required_roll")
    rolled = dice if dice is not None else random.randint(1, 20)
    if rolled < 1 or rolled > 20:
        raise GraphRollError("dice must be between 1 and 20")
    grade = compute_grade(dice=rolled, total=rolled, required_roll=required_roll)
    entry = RollLogEntry(
        id=runtime.progress.next_log_id,
        kind="roll",
        check=_str(pending.get("stat_label"), "stat_label"),
        roll=rolled,
        margin=rolled - required_roll,
        result=_roll_result(grade),
        bonus_breakdown=[BonusItem(label=ROLL_DICE_LABEL, value=rolled)],
    )
    next_progress = runtime.progress.model_copy(
        update={
            "pending_roll": None,
            "turn_count": runtime.progress.turn_count + 1,
            "next_log_id": entry.id + 1,
        }
    )
    next_runtime = runtime.model_copy(
        update={
            "progress": next_progress,
            "log_entries": [*runtime.log_entries, entry],
        }
    )
    await repo.append_log_entries(game_id, [entry])
    await repo.save_progress(next_progress)
    return GraphActionRequestResult(
        runtime=next_runtime,
        status="executed",
        front_state=graph_to_front_state(next_runtime),
    )


def build_pending_roll(
    player_properties: dict[str, Any],
    action: Action,
) -> dict[str, Any]:
    stat = _roll_stat(action)
    label = stat_label(stat)
    stats = player_properties.get("stats")
    stat_value = stats.get(stat, 10) if isinstance(stats, dict) else 10
    required_roll = compute_required_roll(DEFAULT_ROLL_DC, _int(stat_value, stat))
    return {
        "id": f"roll_{secrets.token_hex(4)}",
        "kind": action.verb,
        "title": f"{label} 판정이 필요합니다",
        "body": _roll_body(action),
        "stat": stat,
        "stat_label": label,
        "required_roll": required_roll,
        "payload": {
            "kind": "graph_action",
            "action": action.model_dump(mode="json", by_alias=True),
        },
    }


def _roll_stat(action: Action) -> str:
    if action.verb == "perceive":
        return "mind"
    if action.verb == "speak":
        return "presence"
    if action.verb == "move":
        return "agility"
    return "body"


def _roll_body(action: Action) -> str:
    if action.verb == "perceive":
        return "자세히 살펴보려면 집중해야 합니다."
    if action.verb == "speak":
        return "상대를 움직이려면 말의 무게를 실어야 합니다."
    if action.verb == "move":
        return "발소리를 죽이고 미끄러지지 않아야 합니다."
    return "행동의 결과를 확인해야 합니다."


def _roll_result(grade: str) -> str:
    if grade in {"critical_success", "success"}:
        return "success"
    if grade == "partial_success":
        return "partial"
    return "fail"


def _int(value: object, field: str) -> int:
    if not isinstance(value, int):
        raise GraphRollError(f"{field} must be an integer")
    return value


def _str(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise GraphRollError(f"{field} must be a string")
    return value
