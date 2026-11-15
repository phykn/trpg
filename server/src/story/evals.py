import argparse
import asyncio
import json
import sys
import time
from collections import Counter
from pathlib import Path

import yaml

from ..interpret import Interpreter
from ..models.decision import DecisionClient
from ..rules.state import start_state
from .load import StoryError, load_story, parse_address

GOAL_RIGHT = 0.85
GOAL_WRONG_TOPIC = 0.02


def read_cases(folder, story):
    path = Path(folder) / "evals.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cases = []
    for where, groups in raw.items():
        kind, (name,) = parse_address(where)
        if kind not in ("사람", "곳") or name not in (story.people if kind == "사람" else story.places):
            raise StoryError(f"{path.name}: {where}")
        for expect, texts in groups.items():
            topics = expect.split(" + ")
            known = expect in ("잡담", "넘김") or expect.startswith("곳 ") and expect[2:] in story.places or (
                kind == "사람" and all(t in story.people[name].topics for t in topics))
            if not known:
                raise StoryError(f"{path.name}: {where}: {expect}")
            cases += [(where, expect, text) for text in texts]
    return cases


def make_state(story, where):
    kind, (name,) = parse_address(where)
    state = start_state(story, 0)
    place = story.people[name].place if kind == "사람" else name
    return {**state, "notebook": dict.fromkeys(story.lines, 0), "place": place, "visited": [place],
            "partner": name if kind == "사람" else None}


def show_heard(heard):
    if heard["kind"] == "topics":
        return " + ".join(heard["topics"])
    if heard["kind"] == "move":
        return f"곳 {heard['place']}"
    if heard["kind"] == "unsure":
        return f"되물음 {' / '.join(heard['topics'])}"
    return {"chat": "잡담", "none": "넘김"}[heard["kind"]]


def grade(expect, heard):
    if heard["kind"] == "topics" and set(heard["topics"]) == set(expect.split(" + ")):
        return "맞힘"
    if heard["kind"] == "topics":
        return "틀린 화제" if set(heard["topics"]) - set(expect.split(" + ")) else "모자람"
    if heard["kind"] == "unsure":
        return "되물음"
    return "맞힘" if show_heard(heard) == expect else "틀림"


async def run_evals(folder, interpreter):
    story = load_story(folder)
    results = []
    for where, expect, text in read_cases(folder, story):
        began = time.monotonic()
        heard = await interpreter.read(story, make_state(story, where), text)
        results.append({"where": where, "text": text, "expect": expect, "got": show_heard(heard),
                        "grade": grade(expect, heard), "seconds": round(time.monotonic() - began, 2), "heard": heard})
    return results


def summarize(results):
    counts = Counter(r["grade"] for r in results)
    total = len(results)
    lines = [f"{'O' if r['grade'] == '맞힘' else 'X'} {r['grade']:<5} {r['where']}: {r['text']}  기대={r['expect']}"
             f"  얻음={r['got']}" for r in results]
    lines.append(" · ".join(f"{g} {counts[g]}" for g in ("맞힘", "되물음", "모자람", "틀림", "틀린 화제")) + f" / {total}")
    right, wrong = counts["맞힘"] / total, counts["틀린 화제"] / total
    passed = right >= GOAL_RIGHT and wrong <= GOAL_WRONG_TOPIC
    lines.append(f"{'통과' if passed else '떨어짐'}  맞힘 {right:.0%} (≥ {GOAL_RIGHT:.0%}), "
                 f"틀린 화제 {wrong:.0%} (≤ {GOAL_WRONG_TOPIC:.0%})")
    return "\n".join(lines), passed


def main():
    from run_api import local_settings

    parser = argparse.ArgumentParser(description="Run a story's interpretation evals against the decision model.")
    parser.add_argument("folder", type=Path)
    parser.add_argument("--out", type=Path, help="a run folder under qa_test/runs/ for the report and the answers")
    args = parser.parse_args()
    cfg = local_settings()
    decision = DecisionClient(cfg.decision_base_url, cfg.decision_model)
    results = asyncio.run(run_evals(args.folder, Interpreter(decision)))
    report, passed = summarize(results)
    print(report)
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "report.txt").write_text(report + "\n", encoding="utf-8")
        (args.out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
