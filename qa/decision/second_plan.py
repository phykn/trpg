"""The narration model's reading of the whole plan: every action in order, as option numbers."""
import asyncio
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
sys.path.insert(0, str(Path(__file__).parent))
from bench import SAY, available, load  # noqa: E402
from src.locale import ko  # noqa: E402
from src.models.llm import LLMClient  # noqa: E402

SYSTEM = ("당신은 한국어 TRPG의 입력 분류기입니다. 플레이어 문장이 하는 행동을 일어나는 차례대로 선택지 번호로 적습니다. "
          "한 행동을 여러 말로 풀어 쓴 것은 하나로 셉니다. 번호만 쉼표로 나누어 답합니다.")
PROMPT = "플레이어 문장: {text}\n선택지:\n{options}\n번호:"


async def main(out):
    llm = LLMClient("http://127.0.0.1:8082/v1", model="gemma4")
    done = {json.loads(x)["id"] for x in Path(out).read_text().splitlines()} if Path(out).exists() else set()
    with open(out, "a") as f:
        for item in load():
            if item["kind"] != "sentence" or item["id"] in done:
                continue
            have = available(item["scene"])
            keys = [s for s in SAY if s in have] + [s for s in SAY if s not in have]
            listed = "\n".join(f"{i + 1}. {ko.SCHEMA_ASK[k]}" for i, k in enumerate(keys))
            msgs = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": ko.fill(PROMPT, text=item["text"], options=listed)}]
            t = time.perf_counter()
            raw = await llm.pick(msgs, max_tokens=12)
            ms = (time.perf_counter() - t) * 1000
            nums = [int(x) - 1 for x in re.findall(r"\d+", raw)]
            plan = [keys[i] for i in nums if 0 <= i < len(keys)]
            f.write(json.dumps({"id": item["id"], "raw": raw, "plan": plan, "gold": item["gold"]["steps"], "ms": ms},
                               ensure_ascii=False) + "\n")
            f.flush()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
