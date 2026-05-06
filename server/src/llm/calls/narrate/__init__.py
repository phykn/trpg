"""Narrate chain orchestrator.

stream_narrate(client, input) yields body chunks as NarrativeDelta events while
collecting the full body, then runs the extract stage with body + original
context to produce the metadata. Same external API as the pre-PR3 single-call
narrate — flow code doesn't change.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass

from ...context.surroundings import surroundings_for_extract
from ...client import LLMClient
from .body import stream_body
from .extract import ExtractInput, run_extract
from .schema import NarrateInput, NarrateOutput


def _clean_body(body: str) -> str:
    # Undo JSON-style escapes the LLM occasionally leaks into the body
    # (the body prompt forbids them, but the LLM sometimes slips).
    return (
        body.replace('\\"', '"')
        .replace("\\'", "'")
        .replace("\\n", "\n")
        .replace("\\t", "\t")
    )


@dataclass
class NarrativeDelta:
    text: str


@dataclass
class NarrativeFinal:
    body: str
    output: NarrateOutput
    parse_error: str | None = None


# Legacy export — flow imports it, but post-PR3 the body and JSON tail are separate calls so the token never appears in either stream.
SEPARATOR = "---JSON---"


async def stream_narrate(
    client: LLMClient,
    input_: NarrateInput,
    locale: str,
) -> AsyncIterator[NarrativeDelta | NarrativeFinal]:
    """Body stream → extract → final.

    Body chunks go straight to the caller as NarrativeDelta events; once body
    completes, extract runs against (full body + original context) and the
    result rides home as NarrativeFinal.

    Failure modes:
    - body call dies before any token: stream_body's retry loop handles up
      to 5 retries; LLMUnavailable bubbles up if all fail.
    - body call dies after some tokens: stream_body raises LLMUnavailable;
      we let it propagate (caller has already received partial body).
    - extract fails after 5 retries: run_extract returns empty NarrateOutput;
      we yield NarrativeFinal with parse_error=None (the engine flow already
      tolerates empty metadata as a fallback shape).
    """
    body_chunks: list[str] = []
    async for raw_chunk in stream_body(client, input_, locale):
        cleaned = _clean_body(raw_chunk)
        body_chunks.append(cleaned)
        yield NarrativeDelta(text=cleaned)

    full_body = "".join(body_chunks)

    extract_input = ExtractInput(
        body=full_body,
        judge_result=input_.judge_result,
        surroundings=surroundings_for_extract(input_.surroundings),
        target_view=input_.target_view,
        grade=input_.grade,
        previous_phase_signal=input_.previous_phase_signal,
    )
    output = await run_extract(client, extract_input, locale)
    yield NarrativeFinal(body=full_body, output=output, parse_error=None)


__all__ = [
    "NarrateInput",
    "NarrateOutput",
    "NarrativeDelta",
    "NarrativeFinal",
    "SEPARATOR",
    "stream_narrate",
]
