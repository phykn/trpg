"""The narration model on the same layer-2 questions (intent, target, approach), with Kev's context."""
import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
sys.path.insert(0, str(Path(__file__).parent))
import bench as B  # noqa: E402
from src.models.llm import LLMClient  # noqa: E402

SYSTEM = "당신은 한국어 TRPG의 입력 분류기입니다. 문맥과 플레이어 문장을 읽고 질문에 맞는 답을 선택지에서 번호 하나로 고릅니다. 번호만 답합니다."


async def main(out):
    llm = LLMClient("http://127.0.0.1:8082/v1", model="gemma4")
    done = {(json.loads(x)["id"], json.loads(x)["q"]) for x in Path(out).read_text().splitlines()} if Path(out).exists() else set()
    with open(out, "a") as f:
        for item in B.load():
            if item["kind"] != "sentence":
                continue
            state, qs, golds = B.layer2(item, "base")
            for fam in ("intent", "target", "approach"):
                if fam not in qs or (item["id"], fam) in done:
                    continue
                keys = list(qs[fam]["criteria"])
                listed = "\n".join(f"{i + 1}. {qs[fam]['criteria'][k]}" for i, k in enumerate(keys))
                msgs = [{"role": "system", "content": SYSTEM},
                        {"role": "user", "content": f"{state}\n\n질문: {qs[fam]['instructions']}\n선택지:\n{listed}\n번호:"}]
                raw = await llm.pick(msgs)
                m = re.search(r"\d+", raw)
                i = int(m.group()) - 1 if m else -1
                pick = keys[i] if 0 <= i < len(keys) else None
                f.write(json.dumps({"id": item["id"], "q": fam, "pick": pick, "gold": golds[fam][0]}, ensure_ascii=False) + "\n")
                f.flush()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
