from .._runner import load_prompt, run_with_retries
from ...llm.client import LLMClient
from .schema import SkillRecommendInput, SkillRecommendOutput

_PROMPT = load_prompt(__file__)


async def recommend(
    client: LLMClient,
    input_: SkillRecommendInput,
    retries: int = 5,
) -> SkillRecommendOutput:
    return await run_with_retries(
        client,
        system_prompt=_PROMPT,
        user_payload=input_.model_dump_json(),
        parse=SkillRecommendOutput.model_validate_json,
        retries=retries,
        agent="recommend",
    )
