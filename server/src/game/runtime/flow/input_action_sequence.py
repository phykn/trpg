from collections.abc import Sequence

from src.game.domain.action import Action, ActionCheckHint


def normalize_classified_action_sequence(
    actions: Sequence[Action],
    action_checks: Sequence[ActionCheckHint],
) -> tuple[list[Action], list[ActionCheckHint]]:
    keep_checks = bool(action_checks)
    normalized_actions: list[Action] = []
    normalized_checks: list[ActionCheckHint] = []
    index = 0
    while index < len(actions):
        action = actions[index]
        check_hint = check_hint_at(action_checks, index)
        if action.verb != "perceive" or _requires_classified_check(check_hint):
            normalized_actions.append(action)
            if keep_checks:
                normalized_checks.append(check_hint or ActionCheckHint())
            index += 1
            continue

        targets: list[str] = []
        broad_perception = False
        scan_index = index
        while scan_index < len(actions):
            scan_action = actions[scan_index]
            scan_check = check_hint_at(action_checks, scan_index)
            if scan_action.verb == "perceive" and not _requires_classified_check(
                scan_check
            ):
                values = _action_value_items(scan_action.what)
                if values:
                    for value in values:
                        if value not in targets:
                            targets.append(value)
                else:
                    broad_perception = True
                scan_index += 1
                continue
            if _is_ungrounded_perceive_pass(scan_action):
                scan_index += 1
                continue
            break

        normalized_actions.append(
            action.model_copy(
                update={
                    "what": _merged_action_value(targets, broad=broad_perception),
                }
            )
        )
        if keep_checks:
            normalized_checks.append(check_hint or ActionCheckHint())
        index = scan_index

    return normalized_actions, normalized_checks


def check_hint_at(
    action_checks: Sequence[ActionCheckHint],
    index: int,
) -> ActionCheckHint | None:
    if index >= len(action_checks):
        return None
    return action_checks[index]


def _requires_classified_check(check_hint: ActionCheckHint | None) -> bool:
    return check_hint is not None and check_hint.required


def _action_value_items(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _merged_action_value(targets: list[str], *, broad: bool) -> str | list[str] | None:
    if broad or not targets:
        return None
    if len(targets) == 1:
        return targets[0]
    return targets


def _is_ungrounded_perceive_pass(action: Action) -> bool:
    return (
        action.verb == "pass"
        and isinstance(action.note, str)
        and action.note.startswith("ungrounded action=perceive")
    )
