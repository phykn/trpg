import json
import re

from pydantic import ValidationError

from ..runner import get_prompt, run_with_retries
from ...client import LLMClient
from ...diag import llm_diag
from ...context.classify_view import classify_context_to_grounding_view
from src.locale.generated_story import (
    GENERATED_OPEN_MOVE_TARGET_TERMS,
    GENERATED_OPEN_MOVE_TERMS,
)
from src.locale.render import render
from .grounding import ActionGroundingError, validate_grounded_output
from .schema import Action, ActionOutput, ClassifyInput, validate_action_output_json
from .shortcuts import (
    classify_action_shortcut,
    classify_guard,
)


async def classify(
    client: LLMClient,
    input_: ClassifyInput,
    locale: str,
    retries: int = 5,
    *,
    strict: bool = False,
    temperature: float | None = None,
) -> ActionOutput:
    grounding_view = classify_context_to_grounding_view(input_.context)
    in_combat = input_.context.get("mode") == "combat"
    guard_output = classify_guard(input_.player_input, locale=locale)
    if guard_output is not None:
        return guard_output
    action_shortcut = classify_action_shortcut(
        input_.player_input,
        grounding_view,
        locale=locale,
    )
    if action_shortcut is not None:
        return validate_grounded_output(action_shortcut, grounding_view)

    def parse(answer: str) -> ActionOutput:
        output = validate_action_output_json(
            answer,
            in_combat=in_combat,
            surroundings=grounding_view,
        )
        return validate_grounded_output(output, grounding_view, allow_partial=not strict)

    try:
        return await run_with_retries(
            client,
            system_prompt=get_prompt("classify", locale),
            user_payload=input_.model_dump_json(),
            parse=parse,
            retry_on=(
                ValidationError,
                json.JSONDecodeError,
                ActionGroundingError,
                ValueError,
            ),
            retries=retries,
            agent="classify",
            temperature=temperature,
            correction_hint="re-check the action catalog (required ids, enum fields) and that every id exists in context",
            include_failed_answer=False,
        )
    except (
        ValidationError,
        json.JSONDecodeError,
        ActionGroundingError,
        ValueError,
    ) as e:
        if strict:
            raise
        if isinstance(e, ActionGroundingError):
            return ActionOutput(
                refuse={
                    "category": "invalid_transition",
                    "message_hint": _grounding_rejection_message(str(e), locale),
                    "target": _grounding_rejection_target(str(e)),
                }
            )
        open_move = _open_move_fallback(input_.player_input)
        if open_move is not None:
            return open_move
        llm_diag("llm:classify_fallback", err=type(e).__name__, msg=str(e)[:120])
        return ActionOutput(actions=[Action(verb="pass")])


def _open_move_fallback(player_input: str) -> ActionOutput | None:
    text = player_input.strip()
    if not text:
        return None
    if not any(marker in text for marker in GENERATED_OPEN_MOVE_TERMS):
        return None
    if not any(marker in text for marker in GENERATED_OPEN_MOVE_TARGET_TERMS):
        return None
    return ActionOutput(actions=[Action(verb="move", note="generated_open_move")])


def _grounding_rejection_message(reason: str, locale: str) -> str:
    text = reason.lower()
    if "protected target cannot be attacked" in text:
        return render("log.error.protected_target", locale)
    if "ungrounded action=move" in text:
        return render("log.error.move_unavailable", locale)
    if "item is not carried" in text:
        return render("log.error.item_not_in_inventory", locale)
    if "missing item" in text or "ungrounded action=use" in text:
        return render("log.error.unknown_item", locale)
    return render("log.error.generic_block", locale)


def _grounding_rejection_target(reason: str) -> str | None:
    if "protected target cannot be attacked" not in reason.lower():
        return None
    match = re.search(r"what:\s*\[['\"]([^'\"]+)['\"]\]", reason)
    return match.group(1) if match is not None else None
