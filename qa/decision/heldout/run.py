"""Held-out plan test: Kev's layer 1 (v3 wording, the engine's), the second opinion, and the narration model's list."""
import asyncio
import json
import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
sys.path.insert(0, str(ROOT))
import bench as B  # noqa: E402
from second_plan import PROMPT, SYSTEM  # noqa: E402
from src.interpret import Interpreter  # noqa: E402
from src.locale import ko  # noqa: E402
from src.models.llm import LLMClient  # noqa: E402


def scenes():
    out = {}
    for g in ("fantasy", "horror", "joseon", "mystery", "postapoc", "scifi"):
        seen = []
        for r in map(json.loads, (ROOT / "data" / f"{g}.jsonl").read_text().splitlines()):
            if r["kind"] == "sentence":
                k = json.dumps(r["scene"], sort_keys=True, ensure_ascii=False)
                if k not in seen:
                    seen.append(k)
        for i, k in enumerate(seen):
            out[(g, i)] = json.loads(k)
    return out


async def main():
    sc = scenes()
    items = [json.loads(x) for x in (ROOT / "heldout" / "plan.jsonl").read_text().splitlines() if x.strip()]
    llm = LLMClient("http://127.0.0.1:8082/v1", model="gemma4")
    it2 = Interpreter(decision=None, llm=llm, timeout=60)
    out_dir = Path(__file__).resolve().parents[3] / "qa_test" / "runs" / "decision-1" / "heldout"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = open(out_dir / "answers.jsonl", "w")
    async with httpx.AsyncClient(timeout=60) as c:
        for h in items:
            scene = sc[(h["genre"], h["scene"])]
            item = {"scene": scene, "text": h["text"], "gold": {"steps": h["steps"]}}
            # every later step asked, as the engine does (the bench drops s3 for one-step golds)
            state = B.sentence(h["text"])
            first = {s: ko.SCHEMA_ASK[s] for s in B.SAY if s in B.available(scene)}
            later = {s: ko.SCHEMA_ASK[s] for s in B.SAY}
            qs = {f"s{i}": B.choice(ko.STEP_QUESTION if i == 1 else B.OLD_STEP_QUESTION[i], first if i == 1 else later)
                  for i in (1, 2, 3)}
            qs["n"] = B.choice(ko.COUNT_QUESTION, ko.COUNT)
            kev, ms = await B.decide(c, "http://127.0.0.1:8081", state, qs)
            second = None   # the engine now reads the list instead (interpret.Interpreter.read)
            have = B.available(scene)
            keys = [s for s in B.SAY if s in have] + [s for s in B.SAY if s not in have]
            listed = "\n".join(f"{i + 1}. {ko.SCHEMA_ASK[k]}" for i, k in enumerate(keys))
            raw = await llm.pick([{"role": "system", "content": SYSTEM},
                                  {"role": "user", "content": ko.fill(PROMPT, text=h["text"], options=listed)}], max_tokens=12)
            plan = [keys[i] for i in (int(x) - 1 for x in re.findall(r"\d+", raw)) if 0 <= i < len(keys)]
            out.write(json.dumps({**h, "kev": kev, "kev_ms": ms, "second": second, "llm_plan": plan}, ensure_ascii=False) + "\n")
            out.flush()


if __name__ == "__main__":
    asyncio.run(main())
