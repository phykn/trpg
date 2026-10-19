"""Measure Kev latency for each call interpretation makes, and for asking everything at once.

From server/:  ../.venv/bin/python scripts/bench_kev.py --story harbor --state prison --repeat 5
"""

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER))
sys.path.insert(0, str(SERVER / "scripts"))

from eval_interpret import replay
from src.config import load_server_env
from src.content.load import load_story
from src.interpret import detail_questions, questions, step_questions
from src.models.kev import KevClient
from src.rules.candidates import candidates
from src.scene.build import build

TEXT = "경비 손에 금화를 쥐여 주며 눈감아 달라고 하고 나루를 데리고 나간다"


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--story", default="harbor")
    parser.add_argument("--state", default="prison")
    parser.add_argument("--repeat", type=int, default=5)
    args = parser.parse_args()
    load_server_env(SERVER)
    kev = KevClient(os.environ["KEV_BASE_URL"])
    folder = SERVER.parent / "scenarios" / args.story
    story = load_story(folder).story
    state = replay(story, json.loads((folder / "evals/states" / f"{args.state}.json").read_text()))
    scene = build(story, state)
    cands = candidates(story, state)
    talk = next((c for c in cands if c.startswith("talk:")), "")
    calls = {
        "step call": step_questions(cands),
        "improvise details": detail_questions(story, scene, ["improvise"]),
        "talk details": detail_questions(story, scene, [talk]) if talk else {},
        "everything at once": questions(story, state, scene, cands),
    }
    for name, subset in calls.items():
        if not subset:
            continue
        times = []
        for _ in range(args.repeat):
            started = time.perf_counter()
            await kev.decide(TEXT, subset)
            times.append((time.perf_counter() - started) * 1000)
        print(f"{name:20} {len(subset):3} questions: median {statistics.median(times):6.0f}ms  max {max(times):6.0f}ms")

if __name__ == "__main__":
    asyncio.run(main())
