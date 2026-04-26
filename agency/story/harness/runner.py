"""Race writer 한 사이클 — LLM 호출 + Pydantic 검증 + 자기교정 루프 + 디스크 쓰기."""

import json
import re
from pathlib import Path

from pydantic import ValidationError

from src.domain.entities import Race
from src.llm_client.client import LLMClient

ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,30}$")


class RaceWriterError(Exception):
    """race writer 의 의미 검증 / 디스크 충돌 에러."""


def _load_context(scenario_dir: Path) -> dict:
    world_md = (scenario_dir / "world.md").read_text(encoding="utf-8")
    races_dir = scenario_dir / "races"
    existing = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(races_dir.glob("*.json"))
    ]
    return {"world": world_md, "races": existing}


def _build_system(prompt_path: Path, ctx: dict) -> str:
    base = prompt_path.read_text(encoding="utf-8")
    parts = [
        base,
        "",
        "---",
        "",
        "## 시나리오 world.md",
        "",
        ctx["world"],
        "",
        "## 기존 races (JSON)",
        "",
        json.dumps(ctx["races"], ensure_ascii=False, indent=2),
    ]
    return "\n".join(parts)


def _check_semantics(race: Race, existing_ids: set[str]) -> None:
    if not ID_PATTERN.match(race.id):
        raise RaceWriterError(
            f"race.id={race.id!r} 가 패턴에 안 맞음. ASCII snake_case ([a-z][a-z0-9_]{{1,30}}) 필요."
        )
    if race.id in existing_ids:
        raise RaceWriterError(
            f"race.id={race.id!r} 가 기존 race 와 겹침. 기존: {sorted(existing_ids)}"
        )


async def write_race(
    *,
    client: LLMClient,
    scenario_dir: Path,
    prompt_path: Path,
    hint: str,
    retries: int = 5,
) -> tuple[Race, list[dict]]:
    """race 한 개 생성. 검증 실패 시 자기교정 루프 (retries 회). 모든 messages 반환."""
    ctx = _load_context(scenario_dir)
    existing_ids = {r["id"] for r in ctx["races"]}

    system = _build_system(prompt_path, ctx)
    user_msg = hint.strip() if hint else "(힌트 없음 — 자체 판단으로 한 종족 만들기.)"
    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]
    last_error: Exception | None = None
    for _ in range(retries + 1):
        result = await client.chat(messages=messages, think=False)
        answer = (result["answer"] or "").strip()
        try:
            race = Race.model_validate_json(answer)
            _check_semantics(race, existing_ids)
            return race, messages + [{"role": "assistant", "content": answer}]
        except (ValidationError, RaceWriterError, json.JSONDecodeError) as e:
            last_error = e
            messages.append({"role": "assistant", "content": answer})
            messages.append(
                {
                    "role": "user",
                    "content": f"이전 응답이 검증에 실패했다: {e}. 규칙을 다시 읽고 수정된 JSON 만 출력하라.",
                }
            )
    assert last_error is not None
    raise last_error


def write_race_to_disk(race: Race, scenario_dir: Path) -> Path:
    """scenarios/<scenario>/races/<id>.json 으로 저장. 이미 있으면 RaceWriterError."""
    out_path = scenario_dir / "races" / f"{race.id}.json"
    if out_path.exists():
        raise RaceWriterError(f"{out_path} 가 이미 존재함. 덮어쓰지 않음.")
    out_path.write_text(race.model_dump_json(indent=2), encoding="utf-8")
    return out_path
