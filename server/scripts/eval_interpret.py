"""Score Kev's interpretation on a story's eval set with the real model.

From server/:  ../.venv/bin/python scripts/eval_interpret.py --story harbor [--run name]
Reads scenarios/<story>/evals/interpret.jsonl (or --file, e.g. interpret_holdout.jsonl) and writes qa_test/agency/<run>/interpret.json.
"""

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from datetime import date
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER))

from src.config import load_server_env
from src.content.load import load_story, new_game
from src.interpret import Clarify, Rejected, interpret
from src.models.kev import KevClient
from src.models.qwen import QwenClient
from src.rules.candidates import candidates
from src.rules.resolve import expand, resolve
from src.world.state import ActionStep

SEED = 1


def replay(story, actions: list[str]):
    state = new_game(story, game_id="eval", seed=SEED)
    for action in actions:
        state, _ = resolve(story, state, [ActionStep(action_id=action)], candidates(story, state)[action].label)
    return state


def matches(step, expected: dict) -> bool:
    kind = expected["kind"]
    if kind == "action":
        return step.kind == "action" and step.action_id == expected["id"]
    if step.kind != kind:
        return False
    return all(getattr(step, key) == value for key, value in expected.items() if key != "kind")


def score(result, expect: list[dict], story=None, state=None) -> str:
    if expect[0]["kind"] == "rejected":
        return "right" if isinstance(result, Rejected) else "wrong"
    if isinstance(result, Clarify):
        return "clarify"
    if isinstance(result, Rejected):
        return "rejected"
    # An authored solution is the attempt it stands for: "shoulder the cargo door" may pick the solution
    # with that label instead of a free attempt with the same obstacle and approach.
    raw = result.steps
    if expect[0].get("id", "").startswith("solve:"):
        steps = raw  # the expectation names the solution itself
    else:
        steps = [expand(story, state, s) if story is not None and getattr(s, "action_id", "").startswith("solve:") else s
                 for s in raw]
    ok = len(steps) >= len(expect) and all(matches(s, e) for s, e in zip(steps, expect, strict=False))
    return "right" if ok else "wrong"


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--story", default="harbor")
    parser.add_argument("--run", default=f"{date.today()}-interpret")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--file", default="interpret.jsonl", help="eval file under scenarios/<story>/evals/")
    parser.add_argument("--kev-only", action="store_true", help="without Qwen's second opinion on unsure first steps")
    args = parser.parse_args()
    load_server_env(SERVER)


    qwen = None if args.kev_only else QwenClient(os.environ.get("QWEN_BASE_URL") or "http://127.0.0.1:8082/v1")
    if qwen is not None:
        await qwen.resolve_model()
    kev = KevClient(os.environ["KEV_BASE_URL"], min_confidence=float(os.environ.get("KEV_MIN_CONFIDENCE") or 0.5))
    folder = SERVER.parent / "scenarios" / args.story
    story = load_story(folder).story
    entries = [json.loads(line) for line in (folder / "evals" / args.file).read_text(encoding="utf-8").splitlines() if line.strip()]
    entries = entries[: args.limit or None]
    rows, latencies = [], []
    for entry in entries:
        state = replay(story, json.loads((folder / "evals/states" / f"{entry['state']}.json").read_text()))
        started = time.perf_counter()
        result = await interpret(kev, story, state, entry["text"], qwen)
        latencies.append((time.perf_counter() - started) * 1000)
        verdict = score(result, entry["expect"], story, state)
        improvised = not isinstance(result, Clarify | Rejected) and result.steps[0].kind == "improvise"
        rows.append({**entry, "verdict": verdict, "improvised": improvised, "ms": round(latencies[-1]),
                     "result": result.model_dump()})
        print(f"{verdict:8} {round(latencies[-1]):5}ms  {entry['text']}")
    n = len(rows)
    summary = {
        "story": args.story, "entries": n,
        "accuracy": sum(r["verdict"] == "right" for r in rows) / n,
        "clarify_rate": sum(r["verdict"] == "clarify" for r in rows) / n,
        "wrong_commit_rate": sum(r["verdict"] == "wrong" for r in rows) / n,
        "improvise_rate": sum(r["improvised"] for r in rows) / n,
        "creative_share": sum(bool({"creative", "compound", "nonsense"} & set(r["tags"])) for r in rows) / n,
        "latency_p50_ms": round(statistics.median(latencies)),
        "latency_p95_ms": round(sorted(latencies)[int(0.95 * (n - 1))]),
    }
    out = SERVER.parent / "qa_test/agency" / args.run / "interpret.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print(f"wrote {out}")


if __name__ == "__main__":
    asyncio.run(main())
