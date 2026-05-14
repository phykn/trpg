import random
import secrets
from typing import Any

from src.db.repo import GraphRepo, ScenarioRepo
from src.game.domain.action import Action
from src.game.domain.memory import BonusItem, RollLogEntry
from src.game.rules.dc import compute_grade, compute_required_roll
from src.locale.labels import roll_dice_label, stat_label
from src.locale.render import render
from src.llm.diag import engine_diag, set_diag_context
from src.wire.graph.to_front import graph_to_front_state

from .load import load_runtime_state
from .pending_action import build_pending_action_payload, load_pending_action
from .request_result import (
    GraphActionRequestResult,
    executed_result,
    roll_required_result,
)


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
    *,
    scenario_repo: ScenarioRepo | None = None,
) -> GraphActionRequestResult:
    runtime = await load_runtime_state(repo, game_id, scenario_repo)
    set_diag_context(game_id, runtime.progress.turn_count)
    engine_diag("roll:start", action=action.verb)
    if runtime.progress.pending_roll is not None:
        raise GraphRollActive("a pending_roll is already active")
    if runtime.progress.pending_confirmation is not None:
        raise GraphRollActive("a pending_confirmation is already active")

    pending = build_pending_roll(
        runtime.graph.nodes[runtime.progress.player_id].properties,
        action,
        runtime.progress.locale,
    )
    next_progress = runtime.progress.model_copy(update={"pending_roll": pending})
    next_runtime = runtime.model_copy(update={"progress": next_progress})
    await repo.save_progress(next_progress)
    engine_diag("roll:pending", kind=pending.get("kind"))
    return roll_required_result(
        next_runtime,
        graph_to_front_state(next_runtime),
        pending,
    )


async def run_graph_roll(
    repo: GraphRepo,
    game_id: str,
    roll_id: str,
    *,
    dice: int | None = None,
    scenario_repo: ScenarioRepo | None = None,
) -> GraphActionRequestResult:
    runtime = await load_runtime_state(repo, game_id, scenario_repo)
    set_diag_context(game_id, runtime.progress.turn_count)
    engine_diag("roll:resolve", roll=roll_id)
    pending = runtime.progress.pending_roll
    if pending is None:
        raise GraphRollExpected("no pending_roll")
    if pending.get("id") != roll_id:
        raise GraphRollExpected("roll id mismatch")

    action = load_pending_action(pending, error_type=GraphRollExpected)
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
        bonus_breakdown=[
            BonusItem(
                label=roll_dice_label(runtime.progress.locale),
                value=rolled,
            )
        ],
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
    engine_diag(
        "roll:done",
        action=action.verb,
        result=entry.result,
        rolled=rolled,
        required=required_roll,
        next_turn=next_progress.turn_count,
    )
    return executed_result(
        next_runtime,
        graph_to_front_state(next_runtime),
    )


def build_pending_roll(
    player_properties: dict[str, Any],
    action: Action,
    locale: str = "ko",
) -> dict[str, Any]:
    stat = _roll_stat(action)
    label = stat_label(stat, locale)
    stats = player_properties.get("stats")
    stat_value = stats.get(stat, 10) if isinstance(stats, dict) else 10
    required_roll = compute_required_roll(DEFAULT_ROLL_DC, _int(stat_value, stat))
    return {
        "id": f"roll_{secrets.token_hex(4)}",
        "kind": action.verb,
        "title": render("runtime.roll.title", locale, label=label),
        "body": _roll_body(action, locale),
        "stat": stat,
        "stat_label": label,
        "required_roll": required_roll,
        "payload": build_pending_action_payload(action),
    }


def _roll_stat(action: Action) -> str:
    if action.verb == "perceive":
        return "mind"
    if action.verb == "speak":
        return "presence"
    if action.verb == "move":
        return "agility"
    return "body"


def _roll_body(action: Action, locale: str) -> str:
    if action.verb == "perceive":
        return render("runtime.roll.body.perceive", locale)
    if action.verb == "speak":
        return render("runtime.roll.body.speak", locale)
    if action.verb == "move":
        return render("runtime.roll.body.move", locale)
    return render("runtime.roll.body.default", locale)


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
