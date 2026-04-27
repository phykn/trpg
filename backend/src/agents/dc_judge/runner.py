from pydantic import ValidationError

from .._runner import read_prompt, run_with_retries
from ...llm.client import LLMClient
from .schema import JudgeInput, JudgeOutput, output_adapter
from .semantics import JudgeSemanticError, check_semantics

PROMPT_PATH, _PROMPT = read_prompt(__file__)


async def judge(client: LLMClient, input_: JudgeInput, retries: int = 5) -> JudgeOutput:
    def parse(answer: str) -> JudgeOutput:
        out = output_adapter.validate_json(answer)
        check_semantics(out, input_.surroundings)
        return out

    return await run_with_retries(
        client,
        system_prompt=_PROMPT,
        user_payload=input_.model_dump_json(),
        parse=parse,
        retry_on=(ValidationError, JudgeSemanticError),
        retries=retries,
        agent="dc_judge",
    )
