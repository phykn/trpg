from __future__ import annotations

from src.game.domain.action import Action, ActionCheckHint, ActionOutput

from .types import ActionGroundingError, ViewIds
from .validators import validate_action
from .view import collect_view_ids

__all__ = ["ActionGroundingError", "validate_grounded_output"]


def validate_grounded_output(
    output: ActionOutput,
    surroundings: dict[str, object],
    *,
    allow_partial: bool = False,
) -> ActionOutput:
    if output.actions is None:
        return output
    view = collect_view_ids(surroundings)
    if not allow_partial:
        for action in output.actions:
            validate_action(action, view)
        return output
    return partially_grounded_output(output, view)


def partially_grounded_output(output: ActionOutput, view: ViewIds) -> ActionOutput:
    actions = output.actions or []
    if len(actions) <= 1:
        for action in actions:
            validate_action(action, view)
        return output

    checks = output.action_checks
    keep_checks = bool(checks)
    next_actions: list[Action] = []
    next_checks: list[ActionCheckHint] = []
    valid_original = False
    first_error: ActionGroundingError | None = None
    for index, action in enumerate(actions):
        try:
            validate_action(action, view)
        except ActionGroundingError as exc:
            first_error = first_error or exc
            next_actions.append(Action(verb="pass", note=str(exc)[:120]))
            if keep_checks:
                next_checks.append(ActionCheckHint())
            continue
        valid_original = True
        next_actions.append(action)
        if keep_checks:
            next_checks.append(checks[index])

    if not valid_original and first_error is not None:
        raise first_error
    return ActionOutput.model_validate(
        {
            "actions": [
                action.model_dump(mode="json", by_alias=True)
                for action in next_actions
            ],
            "action_checks": [
                check.model_dump(mode="json") for check in next_checks
            ],
        },
        context={"in_combat": view.in_combat},
    )
