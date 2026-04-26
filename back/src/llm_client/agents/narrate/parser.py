import json
from collections.abc import AsyncIterator
from dataclasses import dataclass

from pydantic import ValidationError

from .schema import NarrateOutput

SEPARATOR = "---JSON---"


@dataclass
class NarrativeDelta:
    text: str


@dataclass
class NarrativeFinal:
    body: str
    output: NarrateOutput


def _clean_body(body: str) -> str:
    """LLM 이 본문에 의도치 않게 박아둔 JSON-style escape 정제.

    `\\"` → `"`, `\\n` → 실제 줄바꿈, `\\\\` → `\\`.
    prompt 에서 금지하지만 보조 안전망.
    """
    return (
        body
        .replace('\\"', '"')
        .replace("\\'", "'")
        .replace("\\n", "\n")
        .replace("\\t", "\t")
    )


def _parse_output(json_text: str) -> NarrateOutput:
    json_text = json_text.strip()
    if not json_text:
        return NarrateOutput()
    try:
        return NarrateOutput.model_validate_json(json_text)
    except (ValidationError, json.JSONDecodeError):
        return NarrateOutput()


async def split_stream(
    tokens: AsyncIterator[str],
) -> AsyncIterator[NarrativeDelta | NarrativeFinal]:
    """Split a token stream into body deltas (yielded incrementally) and a
    final NarrateOutput. Holds back up to len(SEPARATOR)-1 chars so a
    separator straddling two chunks is detected correctly.
    """
    parts: list[str] = []
    yielded = 0
    sep_idx = -1

    async for token in tokens:
        if not token:
            continue
        parts.append(token)
        if sep_idx != -1:
            continue

        full = "".join(parts)
        idx = full.find(SEPARATOR)
        if idx >= 0:
            body_remaining = full[yielded:idx]
            if body_remaining:
                yield NarrativeDelta(text=body_remaining)
            yielded = idx
            sep_idx = idx
        else:
            safe_end = max(yielded, len(full) - len(SEPARATOR) + 1)
            if safe_end > yielded:
                yield NarrativeDelta(text=full[yielded:safe_end])
                yielded = safe_end

    full = "".join(parts)
    if sep_idx == -1:
        if yielded < len(full):
            yield NarrativeDelta(text=full[yielded:])
        body = full
        json_text = ""
    else:
        body = full[:sep_idx]
        json_text = full[sep_idx + len(SEPARATOR):]

    yield NarrativeFinal(body=_clean_body(body), output=_parse_output(json_text))
