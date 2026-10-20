import json
import random
import sys

a_name, b_name, out = sys.argv[1], sys.argv[2], sys.argv[3]
A, B = json.load(open(a_name)), json.load(open(b_name))
rng = random.Random(7)
key, items = {}, []
for x, y in zip(A, B):
    assert (x["run"], x["i"], x["text"]) == (y["run"], y["i"], y["text"])
    if not (x["narration"] and y["narration"]):
        continue
    p = y["narration"]["prompts"][0][1]["content"]
    happened = p[p.index("[일어난 일]"):].split("\n\n")[0]
    context = p[:p.index("[일어난 일]")].strip()
    pair = [("before", x), ("after", y)]
    rng.shuffle(pair)
    iid = f"r{x['run']}t{x['i']}"
    key[iid] = {"A": pair[0][0], "B": pair[1][0], "same_steps": x["steps"] == y["steps"]}
    items.append({"id": iid, "player": x["text"], "context": context, "happened": happened,
                  "A": pair[0][1]["narration"]["text"], "B": pair[1][1]["narration"]["text"]})
json.dump(items, open(out, "w"), ensure_ascii=False, indent=1)
json.dump(key, open(out.replace(".json", ".key.json"), "w"), indent=1)
print(len(items), sum(v["same_steps"] for v in key.values()))
