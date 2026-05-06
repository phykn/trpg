from .._runner import get_prompt, run_with_retries
from ...client import LLMClient
from .schema import SkillRecommendInput, SkillRecommendOutput

_RECOMMEND_TEMPERATURE = 1.0


async def recommend(
    client: LLMClient,
    input_: SkillRecommendInput,
    locale: str,
    retries: int = 5,
) -> SkillRecommendOutput:
    return await run_with_retries(
        client,
        system_prompt=get_prompt(__file__, locale),
        user_payload=input_.model_dump_json(),
        parse=SkillRecommendOutput.model_validate_json,
        retries=retries,
        agent="recommend",
        temperature=_RECOMMEND_TEMPERATURE,
    )
