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
    target_id = payload.get("target_id")

    if command in ("attack", "skill"):
        if not isinstance(target_id, str) or not target_id:
            raise CombatCommandError("target_id is required")
        if target_id not in state.enemy_ids:
            raise CombatCommandError("target is not active enemy")
    elif command not in ("defend", "flee"):
        raise CombatCommandError("unsupported combat command")

    if command == "attack":
        return Action(verb="attack", what=target_id)
    if command == "skill":
        return Action(verb="attack", what=target_id, how="auto")
    if command == "defend":
        return Action(verb="pass", how="defend")
    return Action(verb="move", how="flee")
