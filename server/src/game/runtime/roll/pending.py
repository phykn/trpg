import os
import secrets
from typing import Any

from src.game.domain.action import Action
from src.game.domain.graph import Graph
from src.game.engines.graph.roll import plan_roll_check
from src.game.rules.dc import pick_dc
from src.locale.labels import stat_label
from src.locale.render import render

from ..action_refs import ref_list
from ..pending_action import build_pending_action_payload


def build_pending_roll(
    player_properties: dict[str, Any],
    action: Action,
    locale: str = "ko",
    *,
    graph: Graph | None = None,
    player_id: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    base_dc = _default_roll_dc()
    check = plan_roll_check(
        graph,
        player_properties=player_properties,
        player_id=player_id,
        action=action,
        base_dc=base_dc,
    )
    stat = check.stat
    label = stat_label(stat, locale)
    body = reason or _roll_body(action, locale)
    return {
        "id": f"roll_{secrets.token_hex(4)}",
        "kind": action.verb,
        "title": render("runtime.roll.title", locale, label=label),
        "body": body,
        "check_reason": body,
        "stat": stat,
        "stat_label": label,
        "required_roll": check.required_roll,
        "base_dc": base_dc,
        "effective_dc": check.effective_dc,
        "payload": build_pending_action_payload(action),
    }


def roll_action_target(action: Action) -> str | None:
    for value in (action.what, action.to, action.from_, action.with_):
        strings = ref_list(value)
        if strings:
            return strings[0]
    return None


def _default_roll_dc(default: int = 13) -> int:
    raw = os.getenv("GRAPH_DEFAULT_ROLL_DC")
    if raw is not None:
        try:
            return int(raw)
        except ValueError:
            return default
    return pick_dc("normal")


def _roll_body(action: Action, locale: str) -> str:
    if action.verb == "perceive":
        return render("runtime.roll.body.perceive", locale)
    if action.verb == "speak":
        return render("runtime.roll.body.speak", locale)
    if action.verb == "move":
        return render("runtime.roll.body.move", locale)
    return render("runtime.roll.body.default", locale)
