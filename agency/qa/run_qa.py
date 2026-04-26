"""QA 실행 CLI.

Usage (repo root 또는 어디서나):
    python agency/qa/run_qa.py --agent diplomat --turns 15
    python agency/qa/run_qa.py --agent all --turns 20 --profile default
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# backend/src 의 모듈을 import 할 수 있도록 + run_api.py 도 import 가능
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / "backend" / ".env")

from src.llm_client.client import LLMClient  # noqa: E402

from agency.qa.harness.agent import PlayerAgent  # noqa: E402
from agency.qa.harness.review import (  # noqa: E402
    Verdict,
    review_session,
    write_review_md,
    write_verdict_json,
)
from agency.qa.harness.runner import run_qa_session  # noqa: E402

AGENTS = ["diplomat", "explorer", "provocateur"]


def _agent_prompt_path(name: str) -> Path:
    return ROOT / "agency" / "qa" / "agents" / f"{name}.md"


def _reviewer_prompt_path() -> Path:
    return ROOT / "agency" / "qa" / "agents" / "reviewer.md"


def _write_index(
    index_path: Path,
    *,
    run_id: str,
    profile: str,
    max_turns: int,
    rows: list[tuple[str, dict, Verdict]],
) -> None:
    """run/index.md — agent 별 결과 요약."""
    parts: list[str] = []
    parts.append(f"# QA Run `{run_id}`")
    parts.append(f"- profile: `{profile}`")
    parts.append(f"- max_turns: {max_turns}")
    parts.append("")
    parts.append("| agent | verdict | turns | wins | issues (severity) | errors |")
    parts.append("|-------|---------|-------|------|--------------------|--------|")
    for name, summary, verdict in rows:
        sev_count = {"low": 0, "medium": 0, "high": 0}
        for issue in verdict.issues:
            sev_count[issue.severity] += 1
        sev_str = f"L{sev_count['low']} / M{sev_count['medium']} / H{sev_count['high']}"
        parts.append(
            f"| [{name}](./{name}/review.md) "
            f"| **{verdict.verdict.upper()}** "
            f"| {summary['turn_count']} "
            f"| {len(verdict.wins)} "
            f"| {len(verdict.issues)} ({sev_str}) "
            f"| {summary['error_count']} |"
        )

    parts.append("")
    parts.append("## 즉시 확인 필요 (high)")
    any_high = False
    for name, _summary, verdict in rows:
        for issue in verdict.issues:
            if issue.severity == "high":
                any_high = True
                parts.append(f"- **{name}** [{issue.category}] {issue.summary}")
    if not any_high:
        parts.append("- (없음)")

    parts.append("")
    parts.append("## 권장 점검 (medium)")
    any_med = False
    for name, _summary, verdict in rows:
        for issue in verdict.issues:
            if issue.severity == "medium":
                any_med = True
                parts.append(f"- **{name}** [{issue.category}] {issue.summary}")
    if not any_med:
        parts.append("- (없음)")

    index_path.write_text("\n".join(parts) + "\n", encoding="utf-8")


async def _run_single(
    *,
    agent_name: str,
    run_root: Path,
    profile: str,
    max_turns: int,
    profile_dir: Path,
    llm: LLMClient,
    run_id: str,
) -> tuple[dict, Verdict]:
    agent = PlayerAgent(
        name=agent_name,
        prompt_path=_agent_prompt_path(agent_name),
        llm=llm,
    )
    run_dir = run_root / agent_name
    summary = await run_qa_session(
        agent=agent,
        profile=profile,
        max_turns=max_turns,
        run_dir=run_dir,
        profile_dir=profile_dir,
        llm=llm,
        run_id=run_id,
    )
    verdict, raw = await review_session(
        agent_name=agent_name,
        transcript_path=Path(summary["transcript_path"]),
        final_state_path=Path(summary["final_state_path"]),
        reviewer_prompt_path=_reviewer_prompt_path(),
        llm=llm,
    )
    write_verdict_json(run_dir / "verdict.json", agent_name, run_id, verdict)
    write_review_md(run_dir / "review.md", agent_name, verdict, raw)
    return summary, verdict


async def main_async(args: argparse.Namespace) -> None:
    base_url = os.environ["BASE_URL"]
    llm = LLMClient(base_url=base_url, model="local")

    profile_dir = (ROOT / "backend" / "config" / "profiles").resolve()

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_root = ROOT / "agency" / "qa" / "runs" / run_id
    run_root.mkdir(parents=True, exist_ok=True)

    targets = AGENTS if args.agent == "all" else [args.agent]
    rows: list[tuple[str, dict, Verdict]] = []

    for name in targets:
        print(f"\n━━ {name} 시작 ━━", flush=True)
        summary, verdict = await _run_single(
            agent_name=name,
            run_root=run_root,
            profile=args.profile,
            max_turns=args.turns,
            profile_dir=profile_dir,
            llm=llm,
            run_id=run_id,
        )
        print(
            f"  → {verdict.verdict.upper()} "
            f"(turns={summary['turn_count']}, errors={summary['error_count']}, "
            f"wins={len(verdict.wins)}, issues={len(verdict.issues)})",
            flush=True,
        )
        rows.append((name, summary, verdict))

    _write_index(
        run_root / "index.md",
        run_id=run_id,
        profile=args.profile,
        max_turns=args.turns,
        rows=rows,
    )
    print(f"\n완료. 결과: {run_root}/index.md", flush=True)


def main() -> None:
    p = argparse.ArgumentParser(description="TRPG 게임 QA agent runner")
    p.add_argument(
        "--agent",
        choices=[*AGENTS, "all"],
        default="all",
        help="실행할 agent (기본: all)",
    )
    p.add_argument("--turns", type=int, default=15, help="최대 턴 수 (기본: 15)")
    p.add_argument("--profile", default="default", help="프로필 이름 (기본: default)")
    args = p.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
