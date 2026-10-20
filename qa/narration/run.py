"""Narration bench: a fixed script played with the real models, every narration and its checks recorded.

  python run.py OUT_NAME [--runs 3]
"""
import argparse
import asyncio
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common  # noqa: E402
from src.interpret import Interpreter  # noqa: E402
from src.narrate import Narrator  # noqa: E402
from src.service import GameService  # noqa: E402
from src.story.validate import load_all  # noqa: E402

ROOT = common.RUNS / "narr-2"
SCRIPT = [
    "주위를 천천히 둘러본다",
    "윤슬에게 안녕, 오늘 바다는 어때? 하고 말을 건다",
    "윤슬에게 아버지 배는 언제 돌아오는지 묻는다",
    "윤슬에게 등대 뒤 담장에 대해 물어본다",
    "마을로 내려간다",
    "도해 영감님께 정중하게 인사를 드린다",
    "도해에게 아들의 편지를 건넨다",
    "도해에게 등대 기름이 어디 있는지 묻는다",
    "도해에게 등대 열쇠를 빌려 달라고 부탁한다",
    "등대 앞마당으로 간다",
    "녹슨 문을 자세히 살펴본다",
    "문을 어깨로 힘껏 밀어붙인다",
]
CREATION = {"approaches": {"force": 1, "finesse": 2, "wits": 1, "charm": 0}, "traits": ["sailor", "tinker"]}


class Recording(Narrator):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.log, self.prompts = [], []

    async def write(self, job, draft=None, problems=None):
        from src.narrate import messages
        self.prompts.append(messages(job, draft, problems))
        return await super().write(job, draft, problems)

    def rules(self, job, said, names):
        per, whole = super().rules(job, said, names)
        self.log.append({"said": said, "rules": {str(k): v for k, v in per.items()}, "whole": whole})
        return per, whole

    async def judge(self, job, said, skip):
        out = await super().judge(job, said, skip)
        self.log[-1]["kev"] = {str(k): v for k, v in out.items()}
        return out


async def play(run: int, out: list):
    decision, llm = common.models()
    narrator = Recording(llm, decision)
    tmp = Path(tempfile.mkdtemp())
    svc = GameService(load_all(common.checkout() / "scenarios"), tmp, Interpreter(decision, llm), narrator,
                      seeds=lambda: 7)
    made = await svc.create("r", "lighthouse", CREATION)
    gid, view = made["game_id"], made["view"]
    for i, text in enumerate(SCRIPT):
        res = await svc.command(gid, {"request_id": f"t{i}", "revision": view["revision"], "text": text})
        view = res["view"]
        card = view.get("card")
        if card:
            pick = card["selected"] or card["options"][0]["id"]
            res = await svc.command(gid, {"request_id": f"c{i}", "revision": view["revision"], "card": card["id"],
                                          "pick": pick})
            view = res["view"]
        steps = [s["action"] for s in res.get("steps", [])]
        n = res.get("turn")
        narration = None
        if n is not None:
            narrator.log, narrator.prompts = [], []
            events = [e async for e in await svc.narration(gid, n)]
            narration = next((e for e in events if e["type"] == "result"), None) or \
                {"text": "".join(e.get("text", "") for e in events if e["type"] == "text")}
            u, g = await svc.load(gid)
            narration = {**g.presentation["narration"].get(str(n), {}), "checks": narrator.log, "prompts": narrator.prompts}
        out.append({"run": run, "i": i, "text": text, "steps": steps, "kind": res.get("kind"), "narration": narration})
        print(run, i, steps, (narration or {}).get("text"), flush=True)
    shutil.rmtree(tmp, ignore_errors=True)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--root")
    a = ap.parse_args()
    out = []
    for r in range(a.runs):
        await play(r, out)
        (ROOT / f"{a.name}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    asyncio.run(main())
