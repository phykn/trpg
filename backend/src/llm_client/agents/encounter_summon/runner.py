from pathlib import Path

from pydantic import ValidationError

from ...client import LLMClient
from .schema import EncounterSummonInput, EncounterSummonOutput

PROMPT_PATH = Path(__file__).parent / "prompt.md"


async def encounter_summon(
    client: LLMClient,
    input_: EncounterSummonInput,
    retries: int = 5,
) -> EncounterSummonOutput:
    """LLM 으로 적 한 마리 즉석 생성. 페어 트레이드 위반 시 자기교정 5회."""
    messages: list[dict] = [
        {"role": "system", "content": PROMPT_PATH.read_text(encoding="utf-8")},
        {"role": "user", "content": input_.model_dump_json()},
    ]
    last_error: Exception | None = None
    for _ in range(retries + 1):
        result = await client.chat(messages=messages, think=False)
        answer = result["answer"] or ""
        try:
            return EncounterSummonOutput.model_validate_json(answer)
        except ValidationError as e:
            last_error = e
            messages.append({"role": "assistant", "content": answer})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Your previous response failed validation: {e}. "
                        "Re-read the instructions (especially pair-trade) "
                        "and output only the corrected JSON."
                    ),
                }
            )
    assert last_error is not None
    raise last_error
