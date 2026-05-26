import json

from pydantic import ValidationError

from src.game.domain.story_patch import StoryWriteResponse
from src.llm.calls.runner import get_prompt, run_with_retries
from src.llm.client import LLMClient
from src.llm.context.story_write_context import StoryWriteInput


async def story_write(
    client: LLMClient,
    input_: StoryWriteInput,
    *,
    locale: str,
    retries: int = 5,
) -> StoryWriteResponse:
    def parse(answer: str) -> StoryWriteResponse:
        return StoryWriteResponse.model_validate_json(answer)

    return await run_with_retries(
        client,
        system_prompt=get_prompt("story_write", locale),
        user_payload=input_.model_dump_json(),
        parse=parse,
        retry_on=(ValidationError, json.JSONDecodeError, ValueError),
        retries=retries,
        agent="story_write",
        correction_hint="output only allowed story patch JSON matching the schema",
    )
