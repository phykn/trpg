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
    """Strip JSON-style escapes the LLM sometimes leaks into the body.

    `\\"` → `"`, `\\n` → real newline, `\\\\` → `\\`.
    The prompt forbids this; this is a backup safety net.
    """
    return (
        body.replace('\\"', '"')
        .replace("\\'", "'")
        .replace("\\n", "\n")
        .replace("\\t", "\t")
    )


def _split_trailing_backslashes(s: str) -> tuple[str, str]:
    """Return (safe, hold) where `hold` is a trailing run of backslashes —
    a `\\` straddling a stream chunk boundary would escape whatever arrives
    next, so we hold it back until the next token.
    """
    i = len(s)
    while i > 0 and s[i - 1] == "\\":
        i -= 1
    return s[:i], s[i:]


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
                yield NarrativeDelta(text=_clean_body(body_remaining))
            yielded = idx
            sep_idx = idx
        else:
            safe_end = max(yielded, len(full) - len(SEPARATOR) + 1)
            if safe_end > yielded:
                chunk = full[yielded:safe_end]
                safe_chunk, _hold = _split_trailing_backslashes(chunk)
                if safe_chunk:
                    yield NarrativeDelta(text=_clean_body(safe_chunk))
                    yielded += len(safe_chunk)

    full = "".join(parts)
    if sep_idx == -1:
        if yielded < len(full):
            yield NarrativeDelta(text=_clean_body(full[yielded:]))
        body = full
        json_text = ""
    else:
        body = full[:sep_idx]
        json_text = full[sep_idx + len(SEPARATOR) :]

    yield NarrativeFinal(body=_clean_body(body), output=_parse_output(json_text))
