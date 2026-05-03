from pathlib import Path

from pydantic import ValidationError

from .._runner import load_prompt, run_with_retries
from ...llm.client import LLMClient
from .schema import JudgeInput, JudgeOutput, validate_judge_output
from .semantics import JudgeSemanticError, check_semantics

PROMPT_PATH = Path(__file__).parent / "prompt.md"
_PROMPT = load_prompt(__file__)


async def classify(
    client: LLMClient, input_: JudgeInput, retries: int = 5
) -> JudgeOutput:
    def parse(answer: str) -> JudgeOutput:
        out = validate_judge_output(answer)
        check_semantics(out, input_.surroundings)
        return out

    return await run_with_retries(
        client,
        system_prompt=_PROMPT,
        user_payload=input_.model_dump_json(),
        parse=parse,
        retry_on=(ValidationError, JudgeSemanticError),
        retries=retries,
        agent="classify",
    )
