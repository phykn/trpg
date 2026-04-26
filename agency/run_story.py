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
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / "backend" / ".env")

from src.llm import LLMClient  # noqa: E402

from agency.story.harness.runner import (  # noqa: E402
    SPECS,
    write_entity,
    write_entity_to_disk,
)
from agency.story.harness.scenario import build_scenario  # noqa: E402

SCENARIOS_DIR = ROOT / "scenarios"
AGENTS_DIR = ROOT / "agency" / "story" / "agents"


def _new_run_dir(kind: str) -> Path:
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = ROOT / "reports" / "story" / run_id / f"{kind}_writer"
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


async def _run_scenario(args: argparse.Namespace) -> None:
    scenario_dir = SCENARIOS_DIR / args.name
    prose_path = Path(args.prose).resolve()
    if not prose_path.is_file():
        print(f"줄글 파일 없음: {prose_path}", file=sys.stderr)
        sys.exit(2)
    if scenario_dir.exists():
        print(
            f"시나리오 디렉터리 이미 존재: {scenario_dir} (덮어쓰지 않음)",
            file=sys.stderr,
        )
        sys.exit(2)

    base_url = os.environ["BASE_URL"]
    llm = LLMClient(base_url=base_url, model="local")

    run_dir = _new_run_dir("scenario")
    decompose_prompt = AGENTS_DIR / "_decompose.md"

    def step(msg: str) -> None:
        print(f"  · {msg}", flush=True)

    try:
        result = await build_scenario(
            prose_path=prose_path,
            scenario_dir=scenario_dir,
            decompose_prompt_path=decompose_prompt,
            agents_dir=AGENTS_DIR,
            llm=llm,
            on_step=step,
            run_dir=run_dir,
        )
    except Exception as e:
        (run_dir / "error.txt").write_text(
            f"{type(e).__name__}: {e}\n", encoding="utf-8"
        )
        print(f"실패: {type(e).__name__}: {e}", file=sys.stderr)
        print(f"디버그 로그: {run_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"성공: {result['scenario_dir']}")
    print(f"entity 수: {result['counts']}")
    print(f"디버그 로그: {run_dir}")


def main() -> None:
    p = argparse.ArgumentParser(
        description="Story 팀 — entity 단발 작성 또는 시나리오 한 벌 생성"
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

    sp_scen = sub.add_parser(
        "scenario", help="줄글 한 편으로 시나리오 한 벌 (world.md + 6 entity dir + 메타 3 파일) 생성"
    )
    sp_scen.add_argument("--name", required=True, help="새 시나리오 디렉터리 이름")
    sp_scen.add_argument(
        "--prose", required=True, help="줄글 .md 파일 경로 (분해 입력)"
    )
    sp_scen.set_defaults(func=_run_scenario)

    args = p.parse_args()
    asyncio.run(args.func(args))


if __name__ == "__main__":
    main()
