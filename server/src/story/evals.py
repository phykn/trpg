import argparse
import asyncio
import json
import sys
import time
from collections import Counter
from pathlib import Path

import yaml

from ..config import local_settings
from ..interpret import Interpreter
from ..models.decision import DecisionClient
from ..models.llm import LLMClient
from ..names import show_line, show_name
from ..narrate import Narrator
from ..rules.state import start_state
from ..slots import LEVELS
from .load import StoryError, load_story, parse_address

GOAL_RIGHT = 0.85
GOAL_WRONG_TOPIC = 0.02


def read_cases(folder, story, held=False):
    # evals-held.yaml holds sentences players really typed, kept apart so asks and prompts are never fitted to them
    # (engine/01 5절).
    path = Path(folder) / ("evals-held.yaml" if held else "evals.yaml")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cases = []
    for where, groups in raw.items():
        kind, (name,) = parse_address(where)
        if kind not in ("사람", "곳") or name not in (story.people if kind == "사람" else story.places):
            raise StoryError(f"{path.name}: {where}")
        for expect, texts in groups.items():
            topics = expect.split(" + ")
            known = expect in ("잡담", "넘김", "둘러봄") or expect.startswith("곳 ") and expect[2:] in story.places or (
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
    return {"chat": "잡담", "none": "넘김", "look": "둘러봄"}[heard["kind"]]


def grade(expect, heard):
    if heard["kind"] == "topics" and set(heard["topics"]) == set(expect.split(" + ")):
        return "맞힘"
    if heard["kind"] == "topics":
        return "틀린 화제" if set(heard["topics"]) - set(expect.split(" + ")) else "모자람"
    if heard["kind"] == "unsure":
        return "되물음"
    return "맞힘" if show_heard(heard) == expect else "틀림"


async def run_evals(folder, interpreter, held=False):
    story = load_story(folder)
    results = []
    for where, expect, text in read_cases(folder, story, held):
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


def list_text_jobs(story):
    jobs = []
    for name, person in story.people.items():
        mood = person.attitude
        base = {"kind": "answer", "person": show_name(story, "사람", name), "bio": person.bio,
                "attitude": f"믿음 {LEVELS[mood.trust]}, 두려움 {LEVELS[mood.fear]}"}
        for topic, entry in person.topics.items():
            said = entry.asks[0] if entry.asks else f"{topic}에 관해 묻습니다."
            jobs += [(addr, {**base, "said": said, "says": [line.text], "lines": [line.text], "quiet": False})
                     for addr, line in story.lines.items() if line.kind == "말" and (line.name, line.topic) == (name, topic)]
            if entry.stance == "꺼린다":
                jobs.append((f"꺼림 {name}.{topic}", {**base, "said": said, "says": ["이 화제는 말해 주지 않는다"], "lines": [],
                                                        "quiet": True}))
        jobs.append((f"넘김 {name}", {**base, "said": "이 마을에서 수상한 사람을 본 적 있습니까?", "says": ["답할 것이 없다"], "lines": [],
                                     "quiet": True}))
    for name, place in story.places.items():
        written = [show_line(story, a) for a, line in story.lines.items()
                   if line.kind == "볼 것" and line.place == name and not line.cond and not line.lock]
        people = [show_name(story, "사람", p) for p, person in story.people.items() if person.place == name]
        jobs.append((f"곳 {name}", {"kind": "scene", "place": show_name(story, "곳", name), "desc": place.desc,
                                    "written": written, "happening": [], "people": people}))
    return jobs


async def run_text_evals(folder, narrator):
    results = []
    for label, job in list_text_jobs(load_story(folder)):
        began = time.monotonic()
        async for result in narrator.write(job):
            pass
        results.append({"case": label, "text": result["text"], "checks": result["checks"],
                        "seconds": round(time.monotonic() - began, 1)})
    return results


def summarize_text(results):
    lines = []
    for r in results:
        first, last = r["checks"][0]["failed"], r["checks"][-1]["failed"]
        mark = "통과" if not first else f"다시 씀 {len(r['checks']) - 1}" + (" · 끝내 떨어짐" if last else "")
        lines.append(f"{mark:<12} {r['case']}: {r['text']}  [{', '.join(first) or '-'}]  {r['seconds']}s")
    fails = Counter(f for r in results for f in r["checks"][0]["failed"])
    failed = sum(1 for r in results if r["checks"][0]["failed"])
    still = sum(1 for r in results if r["checks"][-1]["failed"])
    rewrites = sum(len(r["checks"]) - 1 for r in results)
    lines.append(f"첫 글이 떨어짐 {failed}/{len(results)} · 다시 쓴 횟수 {rewrites} · 끝내 떨어짐 {still} · "
                 + " · ".join(f"{k} {v}" for k, v in fails.most_common()))
    return "\n".join(lines)


async def run_text(folder, cfg):
    decision = DecisionClient(cfg.decision_base_url, cfg.decision_model)
    llm = LLMClient(cfg.llm_base_url, cfg.llm_model)
    await llm.check()
    return await run_text_evals(folder, Narrator(llm, decision))


def main():
    parser = argparse.ArgumentParser(description="Run a story's interpretation or text evals against the models.")
    parser.add_argument("folder", type=Path)
    parser.add_argument("--text", action="store_true", help="write and check every answer and scene instead")
    parser.add_argument("--held", action="store_true", help="the held-out sentences players typed, not the working set")
    parser.add_argument("--out", type=Path, help="a run folder under qa_test/runs/ for the report and the answers")
    args = parser.parse_args()
    cfg = local_settings()
    if args.text:
        results = asyncio.run(run_text(args.folder, cfg))
        report, passed = summarize_text(results), True
    else:
        decision = DecisionClient(cfg.decision_base_url, cfg.decision_model)
        results = asyncio.run(run_evals(args.folder, Interpreter(decision), args.held))
        report, passed = summarize(results)
    print(report)
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "report.txt").write_text(report + "\n", encoding="utf-8")
        (args.out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
