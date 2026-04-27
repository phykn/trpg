import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from src.llm import LLMClient


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


def _summarize_final_state(text: str) -> str:
    """Trim the dumped GameState to fields the reviewer actually uses.

    Drops seed-static blocks (race/item/chapter rows, character descriptions and
    learned-skill tables, location descriptions/connections) so the reviewer
    prompt stays inside the LLM ctx window.
    """
    s = json.loads(text)

    def _trim_char(c: dict) -> dict:
        equipment = {k: v for k, v in (c.get("equipment") or {}).items() if v}
        return {
            "name": c.get("name"),
            "alive": c.get("alive"),
            "hp": c.get("hp"),
            "max_hp": c.get("max_hp"),
            "mp": c.get("mp"),
            "max_mp": c.get("max_mp"),
            "location_id": c.get("location_id"),
            "equipment": equipment,
            "inventory_ids": c.get("inventory_ids"),
            "gold": c.get("gold"),
            "xp_pool": c.get("xp_pool"),
            "disposition": c.get("disposition"),
            "relations": c.get("relations"),
            "status": c.get("status"),
            "active_buffs": c.get("active_buffs"),
            "memories": c.get("memories"),
        }

    out = {
        "game_id": s.get("game_id"),
        "profile": s.get("profile"),
        "player_id": s.get("player_id"),
        "active_subject_id": s.get("active_subject_id"),
        "active_quest_id": s.get("active_quest_id"),
        "world_time": s.get("world_time"),
        "turn_count": s.get("turn_count"),
        "pending_check": s.get("pending_check"),
        "combat_state": s.get("combat_state"),
        "characters": {
            cid: _trim_char(c) for cid, c in (s.get("characters") or {}).items()
        },
        "locations": {
            lid: {"name": loc.get("name"), "item_ids": loc.get("item_ids")}
            for lid, loc in (s.get("locations") or {}).items()
        },
        "quests": {
            qid: {"name": q.get("name"), "status": q.get("status")}
            for qid, q in (s.get("quests") or {}).items()
        },
        "turn_log": s.get("turn_log"),
        "recent_dialogue": s.get("recent_dialogue"),
        "log_entries": s.get("log_entries"),
    }
    return json.dumps(out, ensure_ascii=False, indent=2)


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
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
    """Send transcript + final_state to the reviewer LLM and parse a Verdict.

    Returns (Verdict, raw_text). raw_text is reused verbatim when writing review.md.
    """
    transcript = transcript_path.read_text(encoding="utf-8")
    final_state = _summarize_final_state(final_state_path.read_text(encoding="utf-8"))

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
        result = await llm.chat(messages=messages, think=False, agent="qa_reviewer")
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
    # all retries failed — fall back to a minimal verdict
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
    parts: list[str] = []
    parts.append(f"# Review — {agent_name}")
    parts.append(f"**Verdict**: `{verdict.verdict.upper()}`")

    if verdict.wins:
        parts.append("## Wins")
        for w in verdict.wins:
            parts.append(f"- {w}")

    if verdict.issues:
        parts.append("## Issues")
        for issue in verdict.issues:
            head = f"- **[{issue.severity}/{issue.category}]** {issue.summary}"
            parts.append(head)
            for ev in issue.evidence:
                parts.append(f"  - evidence: {ev}")

    if verdict.questions:
        parts.append("## Open questions")
        for q in verdict.questions:
            parts.append(f"- {q}")

    if raw:
        parts.append("---")
        parts.append("## Raw reviewer response")
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
