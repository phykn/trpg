import logging

from pydantic import ValidationError

from ..._runner import load_prompt, run_with_retries
from ....llm.client import LLMClient
from ....rules.permissions import render_for_prompt
from ..schema import NarrateOutput
from .schema import ExtractInput

# {{CHAR_FORBIDDEN}} etc. tokens are substituted at module load (matches old narrate runner — extract owns state_changes permissions).
_PROMPT = load_prompt(__file__, substitutions=render_for_prompt())

_MAX_RETRIES = 5
_EXTRACT_TEMPERATURE = 0.2

_log = logging.getLogger(__name__)


async def run_extract(
    client: LLMClient,
    input_: ExtractInput,
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
            system_prompt=_PROMPT,
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
