import json

from pydantic import ValidationError

from ..runner import get_prompt, run_with_retries
from ...client import LLMClient
from ...diag import llm_diag
from ...context.classify_view import classify_context_to_grounding_view
from .grounding import ActionGroundingError, validate_grounded_output
from .schema import Action, ActionOutput, ClassifyInput, validate_action_output_json
from .shortcuts import (
    classify_action_shortcut,
    classify_dialogue_shortcut,
    classify_guard,
)


async def classify(
    client: LLMClient,
    input_: ClassifyInput,
    locale: str,
    retries: int = 5,
    *,
    strict: bool = False,
    temperature: float = 0.0,
) -> ActionOutput:
    grounding_view = classify_context_to_grounding_view(input_.context)
    in_combat = input_.context.get("mode") == "combat"
    guarded = classify_guard(input_.player_input, locale=locale)
    if guarded is not None:
        return guarded
    action_shortcut = classify_action_shortcut(
        input_.player_input,
        grounding_view,
        locale=locale,
    )
    if action_shortcut is not None:
        return validate_grounded_output(action_shortcut, grounding_view)
    dialogue = classify_dialogue_shortcut(input_.player_input, grounding_view)
    if dialogue is not None:
        return validate_grounded_output(dialogue, grounding_view)

    def parse(answer: str) -> ActionOutput:
        output = validate_action_output_json(
            answer,
            in_combat=in_combat,
            surroundings=grounding_view,
        )
        return validate_grounded_output(output, grounding_view)

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
        llm_diag("llm:classify_fallback", err=type(e).__name__, msg=str(e)[:120])
        return ActionOutput(actions=[Action(verb="pass")])
