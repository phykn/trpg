import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from src.llm_client.client import LLMClient


class Issue(BaseModel):
    severity: Literal["low", "medium", "high"]
    category: str
    summary: str
    evidence: list[str] = []


class Verdict(BaseModel):
    verdict: Literal["pass", "warn", "fail"]
    wins: list[str] = []
    issues: list[Issue] = []
    questions: list[str] = []


def _strip_code_fence(text: str) -> str:
    """LLM 이 ```json ... ``` 로 감싸는 경우 제거."""
    text = text.strip()
    if text.startswith("```"):
        # 첫 줄 (```json 또는 ```) 과 마지막 ``` 제거
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


async def review_session(
    *,
    agent_name: str,
    transcript_path: Path,
    final_state_path: Path,
    reviewer_prompt_path: Path,
    llm: LLMClient,
    retries: int = 3,
) -> tuple[Verdict, str]:
    """transcript + final_state 를 reviewer LLM 에 넘겨 Verdict 받기.

    Returns: (Verdict, raw_text). raw_text 는 review.md 작성에 그대로 사용.
    """
    transcript = transcript_path.read_text(encoding="utf-8")
    final_state = final_state_path.read_text(encoding="utf-8")

    system = reviewer_prompt_path.read_text(encoding="utf-8")
    user_msg = (
        f"QA agent: {agent_name}\n\n"
        "=== 전체 transcript ===\n"
        f"{transcript}\n\n"
        "=== 최종 state ===\n"
        f"{final_state}\n\n"
        "위를 바탕으로 verdict JSON 한 객체만 출력."
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]
    last_error: Exception | None = None
    for _ in range(retries + 1):
        result = await llm.chat(messages=messages, think=False)
        raw = result["answer"] or ""
        cleaned = _strip_code_fence(raw)
        try:
            verdict = Verdict.model_validate_json(cleaned)
            return verdict, raw
        except (ValidationError, ValueError) as e:
            last_error = e
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": (
                    f"앞 응답이 JSON 파싱·검증에 실패했어 ({e}). "
                    "스키마에 맞는 JSON 한 객체만 다시 출력. 코드펜스·설명 금지."
                ),
            })
    # 모두 실패 → 최소 verdict 로 fallback
    fallback = Verdict(
        verdict="warn",
        issues=[
            Issue(
                severity="medium",
                category="기타",
                summary=f"reviewer LLM 출력 파싱 실패 ({type(last_error).__name__})",
                evidence=[],
            )
        ],
    )
    return fallback, ""


def write_review_md(path: Path, agent_name: str, verdict: Verdict, raw: str) -> None:
    """사람-읽기용 review.md."""
    parts: list[str] = []
    parts.append(f"# Review — {agent_name}")
    parts.append(f"**Verdict**: `{verdict.verdict.upper()}`")

    if verdict.wins:
        parts.append("## 잘된 점")
        for w in verdict.wins:
            parts.append(f"- {w}")

    if verdict.issues:
        parts.append("## 이슈")
        for issue in verdict.issues:
            head = f"- **[{issue.severity}/{issue.category}]** {issue.summary}"
            parts.append(head)
            for ev in issue.evidence:
                parts.append(f"  - 근거: {ev}")

    if verdict.questions:
        parts.append("## 의문점")
        for q in verdict.questions:
            parts.append(f"- {q}")

    if raw:
        parts.append("---")
        parts.append("## 원본 reviewer 응답")
        parts.append("```")
        parts.append(raw)
        parts.append("```")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n\n".join(parts) + "\n", encoding="utf-8")


def write_verdict_json(path: Path, agent_name: str, run_id: str, verdict: Verdict) -> None:
    payload = {
        "agent": agent_name,
        "run_id": run_id,
        **verdict.model_dump(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
