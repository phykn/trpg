"""The engine's second opinion (interpret.Interpreter.second) over every sentence item, recorded per item."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
sys.path.insert(0, str(Path(__file__).parent))
from bench import SAY, available, load  # noqa: E402
from src.interpret import Interpreter  # noqa: E402
from src.locale import ko  # noqa: E402
from src.models.llm import LLMClient  # noqa: E402


async def main(out):
    llm = LLMClient("http://127.0.0.1:8082/v1", model="gemma4")
    it = Interpreter(decision=None, llm=llm, timeout=60)
    done = {json.loads(x)["id"] for x in Path(out).read_text().splitlines()} if Path(out).exists() else set()
    with open(out, "a") as f:
        for item in load():
            if item["kind"] != "sentence" or item["id"] in done:
                continue
            first = {s: ko.SCHEMA_ASK[s] for s in SAY if s in available(item["scene"])}
            pick = await it.second(item["text"], first)
            f.write(json.dumps({"id": item["id"], "pick": pick, "gold": item["gold"]["steps"][0]}, ensure_ascii=False) + "\n")
            f.flush()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
