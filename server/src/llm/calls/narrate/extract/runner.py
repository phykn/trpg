import logging

from pydantic import ValidationError

from ..._runner import get_prompt_with_perm_subs, run_with_retries
from ....client import LLMClient
from ..schema import NarrateOutput
from .schema import ExtractInput

_MAX_RETRIES = 3
_EXTRACT_TEMPERATURE = 1.0

_log = logging.getLogger(__name__)


async def run_extract(
    client: LLMClient,
    input_: ExtractInput,
    locale: str,
) -> NarrateOutput:
    """Take body + context, emit metadata JSON. 5-retry on schema failure;
    on exhausted retries, return an empty NarrateOutput so the turn keeps
    advancing — the body already streamed and we'd rather lose state_changes
    than crash the SSE response.

    Empty fallback shape:
      turn_summary="", state_changes=[], memorable=False,
      memory_targets=[], memory={}, memory_links={},
      importance=None
    """
    try:
        return await run_with_retries(
            client,
            system_prompt=get_prompt_with_perm_subs("narrate/extract", locale),
            user_payload=input_.model_dump_json(),
            parse=NarrateOutput.model_validate_json,
            retry_on=(ValidationError,),
            retries=_MAX_RETRIES,
            agent="narrate_extract",
            temperature=_EXTRACT_TEMPERATURE,
        )
    except ValidationError as e:
        _log.warning(
            "narrate.extract retries exhausted; falling back to empty metadata: %s",
            e,
        )
        return NarrateOutput()
