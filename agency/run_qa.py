"""QA runner CLI.

Usage (run from anywhere, repo root included):
    python agency/run_qa.py --agent socialite --turns 25       # single agent
    python agency/run_qa.py --agent all --profile <id>         # all 9 agents x 25T

The runner produces transcripts under qa_test/<agent>/ (transcript.md,
sse.jsonl, final_state.json) plus qa_test/index.md. Game saves are written
to qa_test/<agent>/saves/ via the LocalFs adapter — production Supabase
save tables are never touched. Scenarios are read from Supabase Storage
(same source the production server uses). There is no automated reviewer —
Claude Code reads the artifacts in chat and writes the review there.
"""

import argparse
import asyncio
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# expose server/src and the top-level run_api module to imports
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

# Mirror server/run_api.py:_load_env so SUPABASE_* and BASE_URL / LLM_ROUTE_*
# all resolve here. APP_ENV defaults to dev.
_APP_ENV = os.environ.get("APP_ENV", "dev")
load_dotenv(ROOT / "server" / f".env.{_APP_ENV}")
load_dotenv(ROOT / "server" / ".env.llama_cpp")
load_dotenv(ROOT / "server" / ".env.google")

from src.llm import LLMClient  # noqa: E402

from agency.qa.harness.agent import PlayerAgent  # noqa: E402
from agency.qa.harness.runner import run_qa_session  # noqa: E402

AGENTS: list[str] = [
    "socialite",
    "fighter",
    "shopkeeper",
    "scout",
    "caster",
    "survivor",
    "questor",
    "provocateur",
    "mourner",
]

DEFAULT_TURNS = 25


def _agent_prompt_path(name: str) -> Path:
    return ROOT / "agency" / "qa" / "agents" / f"{name}.md"


def _write_index(
    index_path: Path,
    *,
    run_id: str,
    profile: str,
    max_turns: int,
    rows: list[tuple[str, dict]],
) -> None:
    parts: list[str] = []
    parts.append(f"# QA Run `{run_id}`")
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
    base_url: str,
    run_id: str,
) -> dict:
    run_dir = run_root / agent_name
    # Per-agent LLMClient so request/response logs land under
    # qa_test/<agent>/llm/ — required for qualitative review of each agent's
    # narrate / dc_judge / etc. exchanges.
    llm = LLMClient.from_single(
        base_url=base_url, model="local", log_dir=run_dir / "llm"
    )
    agent = PlayerAgent(
        name=agent_name,
        prompt_path=_agent_prompt_path(agent_name),
        llm=llm,
        max_turns=max_turns,
    )
    return await run_qa_session(
        agent=agent,
        profile=profile,
        max_turns=max_turns,
        run_dir=run_dir,
        llm=llm,
        run_id=run_id,
    )


async def main_async(args: argparse.Namespace) -> None:
    base_url = os.environ["BASE_URL"]

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_root = ROOT / "qa_test"
    run_root.mkdir(parents=True, exist_ok=True)

    if args.agent == "all":
        targets = AGENTS
    else:
        targets = [args.agent]

    # Wipe each target agent's previous run so saves/transcripts don't accumulate.
    # Other agents' directories are left intact, so a single-agent run doesn't
    # clobber an earlier full-suite run.
    for name in targets:
        agent_dir = run_root / name
        if agent_dir.exists():
            shutil.rmtree(agent_dir)

    rows: list[tuple[str, dict]] = []

    for name in targets:
        print(f"\n━━ {name} start ━━", flush=True)
        summary = await _run_single(
            agent_name=name,
            run_root=run_root,
            profile=args.profile,
            max_turns=args.turns,
            base_url=base_url,
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
        rows=rows,
    )
    print(f"\nDone. Results: {run_root}/index.md", flush=True)


def main() -> None:
    p = argparse.ArgumentParser(description="TRPG game QA agent runner")
    p.add_argument(
        "--agent",
        choices=[*AGENTS, "all"],
        default="all",
        help="agent to run (default: all)",
    )
    p.add_argument(
        "--turns",
        type=int,
        default=DEFAULT_TURNS,
        help=f"max turns (default: {DEFAULT_TURNS})",
    )
    p.add_argument("--profile", default="default", help="profile name (default: default)")
    args = p.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
