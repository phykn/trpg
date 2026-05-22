from typing import Any

from src.game.domain.action import Action

from ..state import GameRuntimeState


class CombatCommandError(ValueError):
    pass


def build_combat_command_action(
    runtime: GameRuntimeState,
    payload: dict[str, Any],
) -> Action:
    state = runtime.progress.graph_combat_state
    if state is None or state.outcome != "ongoing":
        raise CombatCommandError("combat is not active")

    command = payload.get("command")
    target = payload.get("target")
    support_id = payload.get("support_id")
    support_kind = payload.get("support_kind")

    targeted_commands = {"attack", "talk"}
    untargeted_commands = {"defend", "flee"}

    if command in targeted_commands:
        if not isinstance(target, str) or not target:
            raise CombatCommandError("target is required")
        if target not in state.enemy_ids:
            raise CombatCommandError("target is not active enemy")
    elif command not in untargeted_commands:
        raise CombatCommandError("unsupported combat command")

    support = _support_id(support_id, support_kind)

    if command == "attack":
        return Action(verb="attack", what=target, with_=support)
    if command == "talk":
        return Action(verb="speak", to=target, with_=support)
    if command == "defend":
        return Action(verb="pass", how="defend", with_=support)
    return Action(verb="move", how="flee", with_=support)


def _support_id(support_id: object, support_kind: object) -> str | None:
    if support_id is None and support_kind is None:
        return None
    if support_id is None or support_kind is None:
        raise CombatCommandError("support_id and support_kind must be provided together")
    if support_kind != "skill":
        raise CombatCommandError("unsupported support kind")
    if not isinstance(support_id, str) or not support_id:
        raise CombatCommandError("support_id is required")
    return support_id
