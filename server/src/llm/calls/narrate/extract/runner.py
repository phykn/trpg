import logging

from pydantic import ValidationError

from ..._runner import get_prompt, run_with_retries
from ....client import LLMClient
from src.game.rules.permissions import render_for_prompt
from ..schema import NarrateOutput
from .schema import ExtractInput

_MAX_RETRIES = 5
_EXTRACT_TEMPERATURE = 0.4

_log = logging.getLogger(__name__)


def _build_prompt(locale: str) -> str:
    base = get_prompt(__file__, locale)
    subs = render_for_prompt(locale)
    for k, v in subs.items():
        base = base.replace("{{" + k + "}}", v)
    return base


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
            system_prompt=_build_prompt(locale),
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
