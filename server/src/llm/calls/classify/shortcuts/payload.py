from __future__ import annotations

from src.game.domain.action import Action, ActionOutput


def action_output(
    actions: list[Action],
    *,
    in_combat: bool = False,
) -> ActionOutput:
    return ActionOutput.model_validate(
        {
            "actions": [
                action.model_dump(mode="json", by_alias=True) for action in actions
            ]
        },
        context={"in_combat": in_combat},
    )
