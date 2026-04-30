"""QA runner CLI.

Usage (run from anywhere, repo root included):
    python agency/run_qa.py --agent diplomat --turns 15           # level 1, single agent
    python agency/run_qa.py --agent all --profile <id>            # level 1 (default), 12 narrow agents x 15T
    python agency/run_qa.py --level 2 --agent all --profile <id>  # level 2, 5 phased agents x 45T

Two agent sets:
- L1 (12 narrow personas, 15 turns) — one focused arc per agent. Default.
- L2 (5 phased personas, 45 turns) — each agent runs 3-4 phases that shift persona.
  citizen folds in the affinity-tracking arc (friendly→hostile on the same NPC).

The runner only produces transcripts (transcript.md, sse.jsonl, final_state.json
under reports/qa/<ts>/<agent>/). There is no automated reviewer — Claude Code
reads those files in chat and writes the review there.
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# expose server/src and the top-level run_api module to imports
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / "server" / ".env")

from src.llm import LLMClient  # noqa: E402

from agency.qa.harness.agent import PlayerAgent  # noqa: E402
from agency.qa.harness.runner import run_qa_session  # noqa: E402

AGENTS_BY_LEVEL: dict[int, list[str]] = {
    1: [
        "diplomat",
        "explorer",
        "scout",
        "provocateur",
        "combatant",
        "quartermaster",
        "caster",
        "survivor",
        "questor",
        "griefer",
        "fleer",
        "searcher",
    ],
    2: [
        "wayfarer",
        "warrior",
        "citizen",
        "artisan",
        "provocateur",
    ],
}

DEFAULT_TURNS_BY_LEVEL: dict[int, int] = {1: 15, 2: 45}

ALL_AGENTS = sorted({a for agents in AGENTS_BY_LEVEL.values() for a in agents})


def _agent_prompt_path(name: str) -> Path:
    return ROOT / "agency" / "qa" / "agents" / f"{name}.md"


def _write_index(
    index_path: Path,
    *,
    run_id: str,
    profile: str,
    max_turns: int,
    level: int,
    rows: list[tuple[str, dict]],
) -> None:
    parts: list[str] = []
    parts.append(f"# QA Run `{run_id}`")
    parts.append(f"- level: {level}")
    parts.append(f"- profile: `{profile}`")
    parts.append(f"- max_turns: {max_turns}")
    parts.append("")
    parts.append("| agent | turns | errors | transcript |")
    parts.append("|-------|-------|--------|------------|")
    for name, summary in rows:
        parts.append(
            f"| {name} "
            f"| {summary['turn_count']} "
            f"| {summary['error_count']} "
            f"| [transcript.md](./{name}/transcript.md) · "
            f"[sse.jsonl](./{name}/sse.jsonl) · "
            f"[final_state.json](./{name}/final_state.json) |"
        )
    parts.append("")
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
) -> dict:
    agent = PlayerAgent(
        name=agent_name,
        prompt_path=_agent_prompt_path(agent_name),
        llm=llm,
        max_turns=max_turns,
    )
    run_dir = run_root / agent_name
    return await run_qa_session(
        agent=agent,
        profile=profile,
        max_turns=max_turns,
        run_dir=run_dir,
        profile_dir=profile_dir,
        llm=llm,
        run_id=run_id,
    )


async def main_async(args: argparse.Namespace) -> None:
    base_url = os.environ["BASE_URL"]
    llm = LLMClient(base_url=base_url, model="local", log_dir=ROOT / "logs")

    profile_dir = (ROOT / "scenarios").resolve()

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_root = ROOT / "reports" / "qa" / run_id
    run_root.mkdir(parents=True, exist_ok=True)

    level_agents = AGENTS_BY_LEVEL[args.level]
    if args.agent == "all":
        targets = level_agents
    else:
        if args.agent not in level_agents:
            raise SystemExit(
                f"agent {args.agent!r} is not in level {args.level} "
                f"(level {args.level} agents: {level_agents})"
            )
        targets = [args.agent]
    rows: list[tuple[str, dict]] = []

    for name in targets:
        print(f"\n━━ {name} start ━━", flush=True)
        summary = await _run_single(
            agent_name=name,
            run_root=run_root,
            profile=args.profile,
            max_turns=args.turns,
            profile_dir=profile_dir,
            llm=llm,
            run_id=run_id,
        )
        print(
            f"  → done (turns={summary['turn_count']}, errors={summary['error_count']})",
            flush=True,
        )
        rows.append((name, summary))

    _write_index(
        run_root / "index.md",
        run_id=run_id,
        profile=args.profile,
        max_turns=args.turns,
        level=args.level,
        rows=rows,
    )
    print(f"\nDone. Results: {run_root}/index.md", flush=True)


def main() -> None:
    p = argparse.ArgumentParser(description="TRPG game QA agent runner")
    p.add_argument(
        "--level",
        type=int,
        choices=[1, 2],
        default=1,
        help="agent set: 1 = 12 narrow personas (15T default), 2 = 5 phased personas (45T default)",
    )
    p.add_argument(
        "--agent",
        choices=[*ALL_AGENTS, "all"],
        default="all",
        help="agent to run (default: all). Must belong to the chosen --level set.",
    )
    p.add_argument(
        "--turns",
        type=int,
        default=None,
        help="max turns (default: 15 for level 1, 45 for level 2)",
    )
    p.add_argument("--profile", default="default", help="profile name (default: default)")
    args = p.parse_args()
    if args.turns is None:
        args.turns = DEFAULT_TURNS_BY_LEVEL[args.level]
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
