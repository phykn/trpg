"""Story 팀 — 시나리오 entity 한 개 작성 CLI.

Usage (repo root 어디서나):
    python agency/story/run_story.py race      --scenario default --hint "달밤에 활동하는 종족"
    python agency/story/run_story.py character --scenario default --hint "은퇴한 노검사"
    python agency/story/run_story.py item      --scenario default --hint "녹슨 단검"
    python agency/story/run_story.py location  --scenario default
    python agency/story/run_story.py quest     --scenario default
    python agency/story/run_story.py chapter   --scenario default
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / "backend" / ".env")

from src.llm_client.client import LLMClient  # noqa: E402

from agency.story.harness.runner import (  # noqa: E402
    SPECS,
    write_entity,
    write_entity_to_disk,
)

SCENARIOS_DIR = ROOT / "scenarios"
AGENTS_DIR = ROOT / "agency" / "story" / "agents"


def _new_run_dir(kind: str) -> Path:
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = ROOT / "agency" / "story" / "runs" / run_id / f"{kind}_writer"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


async def _run_entity(args: argparse.Namespace) -> None:
    kind: str = args.kind
    scenario_dir = SCENARIOS_DIR / args.scenario
    if not scenario_dir.is_dir():
        print(f"시나리오 없음: {scenario_dir}", file=sys.stderr)
        sys.exit(2)

    base_url = os.environ["BASE_URL"]
    llm = LLMClient(base_url=base_url, model="local")

    run_dir = _new_run_dir(kind)
    try:
        entity, messages = await write_entity(
            kind=kind,
            scenario_dir=scenario_dir,
            agents_dir=AGENTS_DIR,
            hint=args.hint,
            llm=llm,
        )
    except Exception as e:
        (run_dir / "error.txt").write_text(
            f"{type(e).__name__}: {e}\n", encoding="utf-8"
        )
        print(f"실패: {type(e).__name__}: {e}", file=sys.stderr)
        print(f"디버그 로그: {run_dir}", file=sys.stderr)
        sys.exit(1)

    with (run_dir / "messages.jsonl").open("w", encoding="utf-8") as f:
        for m in messages:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
    (run_dir / "result.json").write_text(
        entity.model_dump_json(indent=2), encoding="utf-8"
    )
    out_path = write_entity_to_disk(entity, scenario_dir, kind)
    print(f"성공: {out_path}")
    print(f"디버그 로그: {run_dir}")


def main() -> None:
    p = argparse.ArgumentParser(
        description="Story 팀 — 시나리오 entity 한 개 작성"
    )
    sub = p.add_subparsers(dest="kind", required=True)
    for kind in SPECS:
        sp = sub.add_parser(kind, help=f"새 {kind} 한 개 작성")
        sp.add_argument(
            "--scenario", default="default", help="대상 시나리오 디렉터리 이름"
        )
        sp.add_argument(
            "--hint", default="", help=f"새 {kind} 에 대한 한 줄 힌트 (옵션)"
        )
        sp.set_defaults(func=_run_entity)

    args = p.parse_args()
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
