from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import yaml

from ..cards import rely_options
from ..interpret import RELY_SHARE, Interpreter
from ..models.decision import DecisionClient
from ..models.llm import LLMClient
from ..rules.acts import NEUTRAL, parse
from ..rules.roll import rolls
from ..service import fresh_presentation
from .validate import NO_ROLL, Run, _creation, _path, _step, load

IDLE = " (idle)"
FRAGILE = 0.05
# The evals measure interpretation, not latency: with other sessions on the shared models a call ran past the
# service's 10 s and the sentence came out idle (qa_test/runs/evals-gate-head 1).
TIMEOUT = 60.0


def replay(u, at: dict) -> Run:
    paths = u.witnesses["paths"]
    run = Run(u, _creation(u, paths[at["path"]]))
    for st in [*_path(paths, at["path"], "evals")[:at["step"]], *at.get("then", [])]:
        aid, dice = _step(st)
        run.step(parse(aid), dice or NO_ROLL)
    return run


class Watched:
    """A model client that counts the calls that ended without an answer: an error or the interpreter's time limit."""

    def __init__(self, client):
        self.client, self.lost = client, 0

    def __getattr__(self, name):
        return getattr(self.client, name)

    async def decide(self, state, questions):
        return await self.watch(self.client.decide(state, questions))

    async def pick(self, messages):
        return await self.watch(self.client.pick(messages))

    async def watch(self, call):
        try:
            return await call
        except BaseException:           # the time limit cancels the call
            self.lost += 1
            raise


async def interpret(it: Interpreter, u, run: Run, text: str, card: bool = False) -> dict:
    """What the service would do with the sentence, taking each card as it opens: the steps' ids, or why it stopped. With card, also
    what the first rolled step's card offers to rely on (engine.md 4.2), None when no step rolls."""
    g = SimpleNamespace(state=run.s, log=run.log, presentation=fresh_presentation(""))
    out = await it.plan(u, g, text)
    if out.get("refused"):
        return {"kind": "refused", "steps": [], "relies": None, "calls": it.calls}
    steps, calls, kind, last, relies = [], list(it.calls), "plan", None, None
    for st in out["plan"]:
        if "action" not in st:
            it.calls = []
            st = await it.fill(u, g, st)
            calls += it.calls
            if st.get("already"):
                continue
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
        o = run.obs
        rolling = rolls(u, o.facts, o.hist, a)
        if card and relies is None and rolling:
            it.calls = []
            relies = await it.relevant(u, o, g.presentation, a, rely_options(u, o, a), st.get("rely"), text)
            calls += it.calls
        told = a.with_(rely=st["rely"]) if st.get("rely") else a
        steps.append(str(told) + (IDLE if st.get("idle") else ""))
        # A roll card opens with the hinted reliance selected, so the step that runs spends it; a step without a roll
        # opens no card and runs bare, as in the service.
        run.step(told if rolling else a, (6, 6, 0))
        g.state, g.log = run.s, run.log
    if not steps and kind == "plan":
        kind = "refused"                # the service refuses a sentence that ran no step and opened no card
    return {"kind": kind, "steps": steps, "relies": relies, "calls": calls}


def first(got: dict) -> str:
    """The first step, idle for a sentence no model read, or why the sentence stopped."""
    if not got["steps"]:
        return got["kind"]
    return "idle" if got["steps"][0].endswith(IDLE) else got["steps"][0]


def score(expect, got: dict) -> bool:
    if expect in ("refused", "clarify"):
        return got["kind"] == expect
    if expect == "idle" or first(got) == "idle":
        return expect == first(got)
    if isinstance(expect, str) and ":" not in expect:       # a schema: any action of it
        return got["steps"][:1] != [] and got["steps"][0].split(":")[0] == expect
    want = expect if isinstance(expect, list) else [expect]
    return got["steps"][:len(want)] == want


def near(calls: list[dict], theta: float, step_theta: float) -> list[dict]:
    """The answers a threshold decides (engine.md 3.4, 4.2) that lie within FRAGILE of it. The try target and approach
    are left out: the narration model's pick decides them."""
    out = []
    for c in calls:
        claims = []
        for k, q in c["questions"].items():
            probs = c["answers"].get(k) or {}
            if not probs:
                continue
            if q["type"] == "noul":
                claims.append({"q": k, "option": "true", "p": probs.get("true", 0.0), "theta": theta})
            elif k == "rely":
                out += [{"q": k, "option": q["criteria"].get(w, w)[:24], "p": pr, "theta": RELY_SHARE}
                        for w, pr in probs.items() if w != "none"]
            else:
                w, pr = max(probs.items(), key=lambda x: x[1])
                if k == "s1":
                    out.append({"q": k, "option": w, "p": pr, "theta": step_theta})
                elif k == "intent" or k in ("tone", "strain") and w != NEUTRAL[k]:
                    out.append({"q": k, "option": w, "p": pr, "theta": theta})
        if claims:
            out.append(max(claims, key=lambda x: x["p"]))     # only the likeliest claim meets θ
    return [m for m in out if abs(m["p"] - m["theta"]) < FRAGILE]


def gate(rows: list[dict]) -> dict[str, list[dict]]:
    return {
        "regressions": [r for r in rows if not r["ok"] and not r.get("known")],
        "fixes": [r for r in rows if r["ok"] and r.get("known")],
        "unanswered": [r for r in rows if r.get("lost")],
        "fragile": [r for r in rows if r.get("fragile")],
    }


def report(g: dict[str, list[dict]]) -> int:
    """Prints the gate; 1 when a case regressed or a model left one unanswered."""
    for r in g["fragile"]:
        for m in r["fragile"]:
            print(f"fragile    {r['n']:2} {r['text']}: {m['q']} {m['option']} {m['p']:.3f} (threshold {m['theta']})")
    for r in g["fixes"]:
        print(f"fix        {r['n']:2} {r['text']} → {r['got']}: passes now, drop its known ({r['known']})")
    for r in g["regressions"]:
        got, want = (f" relies {r['relies']}", f" relies {r['want_relies']}") if "want_relies" in r else ("", "")
        print(f"regression {r['n']:2} {r['text']} → {r['kind']} {r['got']}{got} (expect {r['expect']}{want})")
    for r in g["unanswered"]:
        print(f"unanswered {r['n']:2} {r['text']}: {r['lost']} model call(s) gave no answer; rerun when the models are free")
    failed = bool(g["regressions"] or g["unanswered"])
    print(f"gate: {'FAIL' if failed else 'pass'} ({len(g['regressions'])} regressions, {len(g['unanswered'])} unanswered, "
          f"{len(g['fixes'])} fixes, {len(g['fragile'])} fragile)")
    return 1 if failed else 0


async def main_async(story: Path, out: Path | None, theta: float, decision: str, llm: str, timeout: float) -> int:
    u = load(story / "story.yaml")
    evals = yaml.safe_load((story / "evals.yaml").read_text(encoding="utf-8"))
    models = Watched(DecisionClient("http://127.0.0.1:8081", model=decision)), \
        Watched(LLMClient("http://127.0.0.1:8082/v1", model=llm))
    it = Interpreter(*models, theta=theta, timeout=timeout)
    await it.decision.check()
    await it.llm.resolve_model()
    rows, tally = [], Counter()
    for i, e in enumerate(evals):
        t0, lost = time.perf_counter(), sum(m.lost for m in models)
        got = await interpret(it, u, replay(u, e["at"]), e["text"], card="relies" in e)
        ms = round((time.perf_counter() - t0) * 1000)
        ok = score(e["expect"], got) and ("relies" not in e or got["relies"] == e["relies"])
        want = e["expect"][0] if isinstance(e["expect"], list) else e["expect"]
        tally["ok"] += ok
        tally["schema"] += first(got).split(":")[0] == want.split(":")[0]
        tally["idle"] += first(got) == "idle"
        tally["clarify"] += got["kind"] == "clarify"
        row = {"n": i + 1, "text": e["text"], "expect": e["expect"], "got": got["steps"], "kind": got["kind"],
               "ok": ok, "known": e.get("known"), "lost": sum(m.lost for m in models) - lost,
               "fragile": near(got["calls"], it.theta, it.step_theta), "ms": ms, "calls": got["calls"]}
        got_relies = want_relies = ""
        if "relies" in e:
            row |= {"relies": got["relies"], "want_relies": e["relies"]}
            got_relies, want_relies = f" relies {got['relies']}", f" relies {e['relies']}"
        rows.append(row)
        print(f"{i + 1:2} {'✓' if ok else '✗'} {ms:5}ms {e['text']} → {got['kind']} {got['steps']}{got_relies} "
              f"(expect {e['expect']}{want_relies}){' [known]' if e.get('known') else ''}")
    n = len(evals)
    g = gate(rows)
    summary = {"n": n, "theta": theta, "accuracy": tally["ok"] / n, "first_schema": tally["schema"] / n,
               "idle": tally["idle"] / n, "clarify": tally["clarify"] / n,
               **{k: [r["n"] for r in v] for k, v in g.items()}}
    print(json.dumps(summary, ensure_ascii=False))
    if out:
        out.mkdir(parents=True, exist_ok=True)
        (out / "evals.json").write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1),
                                        encoding="utf-8")
    return report(g)


def main() -> int:
    parser = argparse.ArgumentParser(description="Interpretation regression gate: a story's evals.yaml against the real "
                                                 "models; exit 1 on a regression or an unanswered case.")
    parser.add_argument("story", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--theta", type=float, default=0.5)
    parser.add_argument("--decision", default="malkuth", help="the decision model the server runs: malkuth")
    parser.add_argument("--llm", default="gemma4", help="the loaded LLM: qwen, gemma4 or minicpm")
    parser.add_argument("--timeout", type=float, default=TIMEOUT, help="seconds a model call may take")
    args = parser.parse_args()
    return asyncio.run(main_async(args.story, args.out, args.theta, args.decision, args.llm, args.timeout))


if __name__ == "__main__":
    raise SystemExit(main())
