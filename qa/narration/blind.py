import json
import random
import sys
from pathlib import Path

HAPPENED = ("[일어난 일]", "[이 장의 일]")      # ko.HEAD happened, and notable for a recap


def rows(path: str) -> dict:
    data = json.loads(Path(path).read_text())
    return {(r["game"], r.get("n", f"recap {r.get('recap')}")): r for r in data["rows"]}


def sections(prompt: str) -> tuple[str, str]:
    at = min(i for h in HAPPENED if (i := prompt.find(h)) >= 0)
    return prompt[:at].strip(), prompt[at:].split("\n\n")[0]


def main(before: str, after: str, out: str):
    a, b = rows(before), rows(after)
    rng = random.Random(7)
    key, items = {}, []
    for k in [k for k in a if k in b]:
        x, y = a[k], b[k]
        context, happened = sections(y["narration"]["prompts"][0][1]["content"])
        pair = [("before", x), ("after", y)]
        rng.shuffle(pair)
        iid = f"g{k[0]}t{k[1]}".replace(" ", "")
        key[iid] = {"A": pair[0][0], "B": pair[1][0], "same_steps": x.get("steps") == y.get("steps")}
        items.append({"id": iid, "player": x.get("text"), "context": context, "happened": happened,
                      "A": pair[0][1]["narration"]["text"], "B": pair[1][1]["narration"]["text"]})
    Path(out).write_text(json.dumps(items, ensure_ascii=False, indent=1))
    Path(out.replace(".json", ".key.json")).write_text(json.dumps(key, indent=1))
    print(len(items), sum(v["same_steps"] for v in key.values()))


if __name__ == "__main__":
    main(*sys.argv[1:4])
