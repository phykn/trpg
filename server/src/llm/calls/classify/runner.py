import json

from pydantic import ValidationError

from .._runner import get_prompt, run_with_retries
from ...client import LLMClient
from .grounding import ActionGroundingError, validate_grounded_output
from .schema import ActionOutput, ClassifyInput, validate_action_output_json

_CLASSIFY_TEMPERATURE = 1.0


async def classify(
    client: LLMClient, input_: ClassifyInput, locale: str, retries: int = 3
) -> ActionOutput:
    in_combat = bool(input_.surroundings.get("in_combat", False))

    def parse(answer: str) -> ActionOutput:
        output = validate_action_output_json(answer, in_combat=in_combat)
        return validate_grounded_output(output, input_.surroundings)

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
    )
