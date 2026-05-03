"""Story team CLI — author one scenario entity, or build a whole scenario from prose.

Usage (run from anywhere, repo root included):
    python agency/run_story.py race      --scenario default --hint "달밤에 활동하는 종족"
    python agency/run_story.py character --scenario default --hint "은퇴한 노검사"
    python agency/run_story.py item      --scenario default --hint "녹슨 단검"
    python agency/run_story.py location  --scenario default
    python agency/run_story.py quest     --scenario default
    python agency/run_story.py chapter   --scenario default
    python agency/run_story.py scenario  --name <new> --prose path/to/prose.md
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

# Mirror server/run_api.py:_load_env so BASE_URL / LLM_ROUTE_* resolve here.
_APP_ENV = os.environ.get("APP_ENV", "dev")
load_dotenv(ROOT / "server" / f".env.{_APP_ENV}")
load_dotenv(ROOT / "server" / ".env.llama_cpp")
load_dotenv(ROOT / "server" / ".env.google")

from src.llm import LLMClient  # noqa: E402

from agency.story.harness.runner import (  # noqa: E402
    SPECS,
    write_entity,
    write_entity_to_disk,
)
from agency.story.harness.scenario import build_scenario  # noqa: E402

SCENARIOS_DIR = ROOT / "scenarios"
AGENTS_DIR = ROOT / "agency" / "story" / "agents"


async def _run_entity(args: argparse.Namespace) -> None:
    kind: str = args.kind
    scenario_dir = SCENARIOS_DIR / args.scenario
    if not scenario_dir.is_dir():
        print(f"scenario not found: {scenario_dir}", file=sys.stderr)
        sys.exit(2)

    base_url = os.environ["BASE_URL"]
    llm = LLMClient.from_single(base_url=base_url, model="local")

    try:
        entity, _messages = await write_entity(
            kind=kind,
            scenario_dir=scenario_dir,
            agents_dir=AGENTS_DIR,
            hint=args.hint,
            llm=llm,
        )
    except Exception as e:
        print(f"failed: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

    out_path = write_entity_to_disk(entity, scenario_dir, kind)
    print(f"success: {out_path}")


async def _run_scenario(args: argparse.Namespace) -> None:
    scenario_dir = SCENARIOS_DIR / args.name
    prose_path = Path(args.prose).resolve()
    if not prose_path.is_file():
        print(f"prose file not found: {prose_path}", file=sys.stderr)
        sys.exit(2)
    if scenario_dir.exists():
        print(
            f"scenario directory already exists: {scenario_dir} (will not overwrite)",
            file=sys.stderr,
        )
        sys.exit(2)

    base_url = os.environ["BASE_URL"]
    llm = LLMClient.from_single(
        base_url=base_url, model="local", chat_timeout_s=600.0
    )

    def step(msg: str) -> None:
        print(f"  · {msg}", flush=True)

    try:
        result = await build_scenario(
            prose_path=prose_path,
            scenario_dir=scenario_dir,
            agents_dir=AGENTS_DIR,
            llm=llm,
            on_step=step,
            think=args.think,
        )
    except Exception as e:
        print(f"failed: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"success: {result['scenario_dir']}")
    print(f"entity count: {result['counts']}")


def main() -> None:
    p = argparse.ArgumentParser(
        description="Story team — author one entity, or build a whole scenario"
    )
    sub = p.add_subparsers(dest="kind", required=True)

    for kind in SPECS:
        sp = sub.add_parser(kind, help=f"author one new {kind}")
        sp.add_argument(
            "--scenario", default="default", help="target scenario directory name"
        )
        sp.add_argument(
            "--hint", default="", help=f"one-line hint for the new {kind} (optional)"
        )
        sp.set_defaults(func=_run_entity)

    sp_scen = sub.add_parser(
        "scenario", help="build a whole scenario from prose (world.md + 7 entity dirs + 3 meta files)"
    )
    sp_scen.add_argument("--name", required=True, help="new scenario directory name")
    sp_scen.add_argument(
        "--prose", required=True, help="path to prose .md file (decomposition input)"
    )
    sp_scen.add_argument(
        "--no-think", dest="think", action="store_false", default=True,
        help="disable LLM thinking (faster, lower quality)",
    )
    sp_scen.set_defaults(func=_run_scenario)

    args = p.parse_args()
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
