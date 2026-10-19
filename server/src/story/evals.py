from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import yaml

from ..interpret import Interpreter
from ..models.decision import DecisionClient
from ..models.llm import LLMClient
from ..rules.acts import parse
from ..service import fresh_presentation
from .validate import Run, _creation, _path, load


def replay(u, at: dict) -> Run:
    paths = u.witnesses["paths"]
    run = Run(u, _creation(u, paths[at["path"]]))
    for st in _path(u, paths, at["path"], "evals")[:at["step"]]:
        aid, dice = (st["do"], st["roll"]) if isinstance(st, dict) else (st, None)
        run.step(parse(aid), tuple(dice) if dice else (1, 1, 0))
    return run


async def interpret(it: Interpreter, u, run: Run, text: str) -> dict:
    """What the service would do with the sentence, without cards: the steps' ids, or why it stopped."""
    g = SimpleNamespace(state=run.s, log=run.log, presentation=fresh_presentation(""))
    out = await it.plan(u, g, text)
    if out.get("refused"):
        return {"kind": "refused", "steps": [], "calls": it.calls}
    steps, calls, kind, last = [], list(it.calls), "plan", None
    for st in out["plan"]:
        if "action" not in st:
            it.calls = []
            st = await it.fill(u, g, st)
            calls += it.calls
            if st.get("refused"):
                kind = "refused" if not steps else kind
                break
            if st.get("clarify"):
                kind = "clarify"
                break
            if "action" not in st:
                break
        if steps and st["action"] == last:
            break
        last = st["action"]
        a = parse(st["action"])
        if st.get("rely"):
            a = a.with_(rely=st["rely"])
        steps.append(str(a) + (" (idle)" if st.get("idle") else ""))
        run.step(parse(st["action"]), (6, 6, 0))
        g.state, g.log = run.s, run.log
    return {"kind": kind, "steps": steps, "calls": calls}


def score(expect, got: dict) -> bool:
    if expect in ("refused", "clarify"):
        return got["kind"] == expect
    want = expect if isinstance(expect, list) else [expect]
    return got["steps"][:len(want)] == want if isinstance(expect, list) else got["steps"][:1] == want


async def main_async(story: Path, out: Path | None, theta: float, decision: str, llm: str) -> int:
    u = load(story / "story.yaml")
    evals = yaml.safe_load((story / "evals.yaml").read_text(encoding="utf-8"))
    it = Interpreter(DecisionClient("http://127.0.0.1:8081", model=decision),
                     LLMClient("http://127.0.0.1:8082/v1", model=llm), theta=theta)
    await it.decision.check()
    await it.llm.resolve_model()
    rows, tally = [], Counter()
    for i, e in enumerate(evals):
        t0 = time.perf_counter()
        got = await interpret(it, u, replay(u, e["at"]), e["text"])
        ms = round((time.perf_counter() - t0) * 1000)
        ok = score(e["expect"], got)
        first = got["steps"][0] if got["steps"] else got["kind"]
        want = e["expect"][0] if isinstance(e["expect"], list) else e["expect"]
        tally["ok"] += ok
        tally["schema"] += first.split(":")[0] == want.split(":")[0]
        tally["idle"] += first.endswith("(idle)")
        tally["clarify"] += got["kind"] == "clarify"
        rows.append({"n": i + 1, "text": e["text"], "expect": e["expect"], "got": got["steps"], "kind": got["kind"],
                     "ok": ok, "ms": ms, "calls": got["calls"]})
        print(f"{i + 1:2} {'✓' if ok else '✗'} {ms:5}ms {e['text']} → {got['kind']} {got['steps']} (expect {e['expect']})")
    n = len(evals)
    summary = {"n": n, "theta": theta, "accuracy": tally["ok"] / n, "first_schema": tally["schema"] / n,
               "idle": tally["idle"] / n, "clarify": tally["clarify"] / n}
    print(json.dumps(summary, ensure_ascii=False))
    if out:
        out.mkdir(parents=True, exist_ok=True)
        (out / "evals.json").write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1),
                                        encoding="utf-8")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Interpretation accuracy on a story's evals.yaml against the real models.")
    parser.add_argument("story", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--theta", type=float, default=0.5)
    parser.add_argument("--decision", default="malkuth", help="the decision model the server runs: kev or malkuth")
    parser.add_argument("--llm", default="gemma4", help="the loaded LLM: qwen, gemma4 or minicpm")
    args = parser.parse_args()
    return asyncio.run(main_async(args.story, args.out, args.theta, args.decision, args.llm))


if __name__ == "__main__":
    raise SystemExit(main())
