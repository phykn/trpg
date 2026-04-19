from pathlib import Path

from pydantic import ValidationError

from ...client import LLMClient
from .schema import JudgeInput, JudgeOutput, output_adapter
from .semantics import JudgeSemanticError, check_semantics

PROMPT_PATH = Path(__file__).parent / "prompt.md"


async def judge(
    client: LLMClient, input_: JudgeInput, retries: int = 5
) -> JudgeOutput:
    messages: list[dict] = [
        {"role": "system", "content": PROMPT_PATH.read_text(encoding="utf-8")},
        {"role": "user", "content": input_.model_dump_json()},
    ]
    last_error: Exception | None = None
    for _ in range(retries + 1):
        result = await client.chat(messages=messages, think=False)
        answer = result["answer"] or ""
        try:
            output = output_adapter.validate_json(answer)
            check_semantics(output, input_.surroundings)
            return output
        except (ValidationError, JudgeSemanticError) as e:
            last_error = e
            messages.append({"role": "assistant", "content": answer})
            messages.append(
                {
                    "role": "user",
                    "content": f"Your previous response failed validation: {e}. Re-read the instructions and output only the corrected JSON.",
                }
            )
    assert last_error is not None
    raise last_error
