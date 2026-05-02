from .._runner import load_prompt, run_with_retries
from ...llm.client import LLMClient
from .schema import EncounterSummonInput, EncounterSummonOutput

_PROMPT = load_prompt(__file__)


async def encounter_summon(
    client: LLMClient,
    input_: EncounterSummonInput,
    retries: int = 5,
) -> EncounterSummonOutput:
    """Generate one ad-hoc enemy. Pair-trade violations trigger 5 retries."""
    return await run_with_retries(
        client,
        system_prompt=_PROMPT,
        user_payload=input_.model_dump_json(),
        parse=EncounterSummonOutput.model_validate_json,
        retries=retries,
        correction_hint="especially pair-trade",
        agent="encounter_summon",
    )
