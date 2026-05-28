import json

from pydantic import ValidationError

from src.game.domain.story_patch import StoryWriteResponse
from src.llm.calls.runner import get_prompt, run_with_retries
from src.llm.client import LLMClient
from src.llm.context.story_write_context import StoryWriteInput


async def story_write(
    client: LLMClient,
    input_: StoryWriteInput,
    *,
    locale: str,
    retries: int = 5,
) -> StoryWriteResponse:
    def parse(answer: str) -> StoryWriteResponse:
        return StoryWriteResponse.model_validate(_normalize_story_write_json(answer))

    return await run_with_retries(
        client,
        system_prompt=get_prompt("story_write", locale),
        user_payload=input_.model_dump_json(),
        parse=parse,
        retry_on=(ValidationError, json.JSONDecodeError, ValueError),
        retries=retries,
        agent="story_write",
        correction_hint="output only allowed story patch JSON matching the schema",
    )


def _normalize_story_write_json(answer: str) -> dict:
    raw = json.loads(answer)
    if not isinstance(raw, dict):
        return raw
    raw = {**raw, "new_terms": _normalize_new_terms(raw.get("new_terms"))}
    patches = raw.get("patches")
    if not isinstance(patches, list):
        return raw
    return {
        **raw,
        "patches": [
            _normalize_patch(patch, index=index) for index, patch in enumerate(patches)
        ],
    }


def _normalize_new_terms(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for term in value:
        if isinstance(term, str) and term:
            out.append(term)
        elif isinstance(term, dict):
            for key in ("term", "name", "title", "value"):
                candidate = term.get(key)
                if isinstance(candidate, str) and candidate:
                    out.append(candidate)
                    break
    return out[:4]


def _normalize_patch(patch: object, *, index: int) -> object:
    if not isinstance(patch, dict) or "op" in patch or "type" not in patch:
        return patch
    op = patch.get("type")
    data = patch.get("data") if isinstance(patch.get("data"), dict) else {}
    merged = {**patch, **data, "op": op}
    merged.pop("type", None)
    merged.pop("data", None)
    if op == "add_memory":
        _copy_first(merged, "id", ("id",))
        _default_id(merged, "mem", index)
        _copy_first(merged, "summary", ("summary", "content", "value", "details"))
        return _only_fields(
            merged,
            {"op", "id", "summary", "stability", "visibility"},
        )
    elif op == "add_clue":
        _copy_first(merged, "id", ("id",))
        _default_id(merged, "clue", index)
        _copy_first(merged, "summary", ("summary", "description", "content", "details"))
        _copy_first(merged, "title", ("title", "name", "summary", "description"))
        return _only_fields(
            merged,
            {"op", "id", "title", "summary", "anchor_id", "stability", "visibility"},
        )
    elif op == "add_quest_beat":
        _copy_first(merged, "id", ("id",))
        _default_id(merged, "quest", index)
        _copy_first(merged, "summary", ("summary", "description", "content", "details"))
        _copy_first(merged, "title", ("title", "name", "summary", "description"))
        return _only_fields(merged, {"op", "id", "title", "summary", "stability"})
    return merged


def _only_fields(source: dict, allowed: set[str]) -> dict:
    return {key: value for key, value in source.items() if key in allowed}


def _default_id(target: dict, prefix: str, index: int) -> None:
    if isinstance(target.get("id"), str) and target["id"]:
        return
    target["id"] = f"{prefix}_generated_{index + 1}"


def _copy_first(target: dict, field: str, candidates: tuple[str, ...]) -> None:
    if isinstance(target.get(field), str) and target[field]:
        return
    for candidate in candidates:
        value = target.get(candidate)
        if isinstance(value, str) and value:
            target[field] = value
            return
