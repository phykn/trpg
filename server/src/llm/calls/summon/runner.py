from .._runner import get_prompt, run_with_retries
from ...client import LLMClient
from .schema import EncounterSummonInput, EncounterSummonOutput

_SUMMON_TEMPERATURE = 1.0


async def summon(
    client: LLMClient,
    input_: EncounterSummonInput,
    locale: str,
    retries: int = 5,
) -> EncounterSummonOutput:
    """Generate one ad-hoc enemy. Pair-trade violations trigger 5 retries."""
    return await run_with_retries(
        client,
        system_prompt=get_prompt("summon", locale),
        user_payload=input_.model_dump_json(),
        parse=EncounterSummonOutput.model_validate_json,
        retries=retries,
        correction_hint="especially pair-trade",
        agent="summon",
        temperature=_SUMMON_TEMPERATURE,
    )
