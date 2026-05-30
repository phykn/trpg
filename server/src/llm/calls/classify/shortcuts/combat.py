from __future__ import annotations

from typing import Any

from src.game.domain.action import Action, ActionOutput, RefuseReason
from src.locale.render import render

from .surroundings import dict_entries, entry_ref, named_entry


def protected_attack_refusal(
    player_input: str,
    surroundings: dict[str, Any],
    *,
    locale: str,
) -> ActionOutput | None:
    protected_targets = [
        entry
        for entry in dict_entries(surroundings.get("entities"))
        if entry.get("type") in {"npc", "enemy"} and entry.get("protected") is True
    ]
    target = named_entry(player_input, protected_targets)
    if target is None and len(protected_targets) == 1:
        has_attackable_target = any(
            entry.get("type") in {"npc", "enemy"}
            and entry.get("protected") is not True
            for entry in dict_entries(surroundings.get("entities"))
        )
        if not has_attackable_target:
            target = entry_ref(protected_targets[0])
    if target is None:
        return None
    return ActionOutput(
        refuse=RefuseReason(
            category="invalid_transition",
            message_hint=render("log.error.protected_target", locale),
            target=target["id"],
        )
    )


def attack_action(
    player_input: str,
    surroundings: dict[str, Any],
) -> Action | None:
    target = named_entry(
        player_input,
        [
            entry
            for entry in dict_entries(surroundings.get("entities"))
            if entry.get("type") in {"npc", "enemy"}
            and entry.get("protected") is not True
        ],
    )
    if target is None:
        return None
    skill = named_entry(player_input, dict_entries(surroundings.get("skills")))
    return Action(
        verb="attack",
        what=[target["id"]],
        with_=skill["id"] if skill is not None else None,
    )
