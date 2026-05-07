import json

from pydantic import ValidationError

from .._runner import get_prompt, run_with_retries
from ...client import LLMClient
from .schema import JudgeInput, JudgeOutput, validate_judge_output

_CLASSIFY_TEMPERATURE = 0.4


async def classify(
    client: LLMClient, input_: JudgeInput, locale: str, retries: int = 3
) -> JudgeOutput:
    in_combat = bool(input_.surroundings.get("in_combat", False))

    def parse(answer: str) -> JudgeOutput:
        return validate_judge_output(answer, in_combat=in_combat)

    return await run_with_retries(
        client,
        system_prompt=get_prompt("classify", locale),
        user_payload=input_.model_dump_json(),
        parse=parse,
        retry_on=(ValidationError, json.JSONDecodeError),
        retries=retries,
        agent="classify",
        temperature=_CLASSIFY_TEMPERATURE,
        correction_hint="re-check the verb catalog (required, enum, target_ids) and that every id exists in surroundings",
    )
