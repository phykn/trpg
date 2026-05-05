"""Body-cleaning helper used by the narrate chain orchestrator.

`_clean_body` undoes JSON-style escapes that the LLM occasionally leaks into
the body (the body prompt forbids them, but the LLM sometimes slips). The
old split_stream / NarrativeDelta / NarrativeFinal types now live in
__init__.py — keep importing them from `llm.calls.narrate` (not parser).
"""


def _clean_body(body: str) -> str:
    return (
        body.replace('\\"', '"')
        .replace("\\'", "'")
        .replace("\\n", "\n")
        .replace("\\t", "\t")
    )
