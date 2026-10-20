"""Interpretation of sentences at chosen states, with every model question and answer.

  python probe.py CASES.yaml [--story ID] [--root CHECKOUT]

A case: {at: {path, step}, then: [action ids run after the path], text, expect}. Like story evals, without cards.
"""
import asyncio
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common  # noqa: E402
from src.interpret import Interpreter  # noqa: E402
from src.rules.acts import parse  # noqa: E402
from src.story.evals import interpret, replay, score  # noqa: E402
from src.story.validate import load_all  # noqa: E402


class Logged(Interpreter):
    async def read(self, text, options):
        out = await super().read(text, options)
        self.notes.append(f"read {out}")
        return out

    async def pick(self, state, question, options):
        out = await super().pick(state, question, options)
        self.notes.append(f"pick {out} of {list(options)}")
        return out


async def main():
    cases = yaml.safe_load(Path(sys.argv[1]).read_text())
    u = common.story(load_all(common.checkout() / "scenarios"))
    it = Logged(*common.models())
    rows = []
    for c in cases:
        run = replay(u, c["at"])
        for a in c.get("then", []):
            run.step(parse(a), (6, 6, 0))
        it.notes = []
        got = await interpret(it, u, run, c["text"])
        ok = score(c["expect"], got)
        print(f"{'✓' if ok else '✗'} {c['text']} → {got['kind']} {got['steps']} (expect {c['expect']})")
        for call in got["calls"]:
            print("    ", json.dumps({k: {o: round(p, 2) for o, p in v.items() if p >= 0.02}
                                     for k, v in call["answers"].items()}, ensure_ascii=False))
        for n in it.notes:
            print("    ", n)
        rows.append({**c, "got": got["steps"], "kind": got["kind"], "ok": ok})
    print(f"{sum(r['ok'] for r in rows)}/{len(rows)}")


if __name__ == "__main__":
    asyncio.run(main())
