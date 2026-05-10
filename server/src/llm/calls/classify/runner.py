import json

from pydantic import ValidationError

from .._runner import get_prompt, run_with_retries
from ...client import LLMClient
from ...diag import llm_diag
from .grounding import ActionGroundingError, validate_grounded_output
from .schema import Action, ActionOutput, ClassifyInput, validate_action_output_json

_CLASSIFY_TEMPERATURE = 0.0


async def classify(
    client: LLMClient,
    input_: ClassifyInput,
    locale: str,
    retries: int = 5,
    *,
    strict: bool = False,
) -> ActionOutput:
    in_combat = bool(input_.surroundings.get("in_combat", False))

    def parse(answer: str) -> ActionOutput:
        output = validate_action_output_json(answer, in_combat=in_combat)
        return validate_grounded_output(output, input_.surroundings)

    try:
        return await run_with_retries(
            client,
            system_prompt=get_prompt("classify", locale),
            user_payload=input_.model_dump_json(),
            parse=parse,
            retry_on=(ValidationError, json.JSONDecodeError, ActionGroundingError),
            retries=retries,
            agent="classify",
            temperature=_CLASSIFY_TEMPERATURE,
            correction_hint="re-check the action catalog (required ids, enum fields) and that every id exists in surroundings",
            include_failed_answer=False,
        )
    except (ValidationError, json.JSONDecodeError, ActionGroundingError) as e:
        if strict:
            raise
        llm_diag("llm:classify_fallback", err=type(e).__name__, msg=str(e)[:120])
        return ActionOutput(actions=[Action(verb="pass")])
