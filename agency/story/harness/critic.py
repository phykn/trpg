"""Critic agent — one think=False pass over a freshly written entity.

Pure semantic / tone evaluator. Hard rules (pair-trade, HP/MP formula, slot
matching, etc.) are already enforced by `backend.engines.invariants`; the
critic complements that with judgement on coherence with `world.md`, role,
and the rest of the manifest.

Returns CriticOutput. Failure to parse the critic's JSON is treated as
ok=True (advisory: never block the build on critic errors).
"""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ValidationError

from src.llm import LLMClient


class CriticOutput(BaseModel):
    ok: bool
    feedback: str = ""


async def run_critic(
    *,
    entity_kind: str,
    entity_json: str,
    world_md: str,
    decomp_summary: str,
    prompt_path: Path,
    llm: LLMClient,
    parse_retries: int = 2,
) -> CriticOutput:
    """Single critic pass. think=False (cheap, fast).

    parse_retries covers JSON-parse failure of the critic's own output
    (rare). Semantic NG goes back to the writer's self-correction loop, not
    here — this function returns the verdict and the caller decides.
    """
    system = prompt_path.read_text(encoding="utf-8")
    user = (
        f"## entity 종류\n{entity_kind}\n\n"
        f"## 시나리오 world.md\n{world_md}\n\n"
        f"## 시나리오 명단 요약\n{decomp_summary}\n\n"
        f"## 작성된 entity JSON\n{entity_json}\n"
    )
    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    for _ in range(parse_retries + 1):
        result = await llm.chat(
            messages=messages, think=False, agent=f"story_critic_{entity_kind}"
        )
        answer = (result["answer"] or "").strip()
        try:
            return CriticOutput.model_validate_json(answer)
        except (ValidationError, ValueError):
            messages.append({"role": "assistant", "content": answer})
            messages.append({
                "role": "user",
                "content": "출력이 유효한 JSON 이 아니다. ok·feedback 두 키만 가진 JSON 객체 한 개만 출력하라.",
            })
    return CriticOutput(ok=True, feedback="")
