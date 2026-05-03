"""Shared atoms for the story-team harness — things every step needs (the
error type, id pattern, quest-trigger schema, code-fence stripper). Lives
outside `runner.py` so `decompose.py` and `critic.py` don't have to import
from the writer module just to reach a shared constant."""

import re


ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,30}$")


TRIGGER_TARGET_KIND = {
    "character_death": "character",
    "location_enter": "location",
    "item_use": "item",
}


class EntityWriterError(Exception):
    """Raised on semantic-validation failures or on-disk conflicts."""


def strip_code_fences(text: str) -> str:
    """Strip leading/trailing ```...``` fences if present. Smaller local models
    sometimes emit fenced JSON despite explicit "no fences" instructions; the
    pipeline normalizes the response shape rather than relying on prompt
    discipline."""
    s = text.strip()
    if not s.startswith("```"):
        return s
    lines = s.splitlines()
    if lines[0].lstrip("`").strip().lower() in ("", "json"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()
