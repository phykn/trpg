"""Decision-model benchmark for the engine's closed questions, over story-agnostic genre items.

  python bench.py run MODEL [--variants base,ko_keys,...] [--url URL] [--only fantasy,...]
  python bench.py score [--models a,b] [--by genre]

`base` reproduces the engine's current requests (interpret.py, narrate.py) with its own strings (locale/ko.py).
"""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from src.locale import ko  # noqa: E402

ROOT = Path(__file__).parent
RUNS = Path(__file__).resolve().parents[2] / "qa_test" / "runs" / "decision-1"   # recordings stay out of git
# The engine's strings when `base` was recorded; ko.py has moved on, `base` must not.
OLD_END = "더 하는 것이 없다"
OLD_STEP_QUESTION = {1: "플레이어 문장이 맨 처음 하려는 일은 무엇입니까?",
                     2: "그 다음에 이어서 하는 일은 무엇입니까?",
                     3: "그 다음에 또 이어서 하는 일은 무엇입니까?"}
OLD_CHECK = {"contradicts": "이 문장은 문맥의 사실과 어긋납니까?",
             "invents": "이 문장은 문맥에 없는 사람, 물건, 길을 지어냈습니까?"}
OLD_YES, OLD_NO = "그렇다", "아니다"
OLD_NO_CLAIM, OLD_CLAIM_Q = "거짓 주장이 없음", "플레이어는 어떤 거짓 주장을 합니까?"
SAY = ("go", "look", "take", "give", "talk", "try", "declare", "cut", "choose")
THETA = 0.5
RELY_SHARE = 0.1

# ---------------------------------------------------------------- option wording per variant

KO_KEYS = {
    "step": {"go": "이동", "look": "살피기", "take": "줍기", "give": "건네기", "talk": "대화", "try": "시도",
             "declare": "선언", "cut": "시간 보내기", "choose": "선택", "end": "끝"},
    "approach": dict(ko.APPROACHES),
    "strain": {"natural": "자연스러움", "forced": "무리", "impossible": "불가능"},
    "tone": {"polite": "정중", "friendly": "친근", "plead": "간청", "threaten": "위협", "deceive": "거짓"},
}
EXAMPLES = {
    "go": "어딘가로 간다 (예: 북쪽 문으로 나간다, 위층으로 올라가자)",
    "look": "무언가를 살피거나 읽어 보며, 그것이 어떤지 알아본다 (예: 상자 안을 들여다본다, 여기 뭐가 있지?)",
    "take": "무언가를 집는다 (예: 바닥의 칼을 줍는다)",
    "give": "누군가에게 무언가를 건넨다 (예: 문지기에게 동전을 쥐여 준다)",
    "talk": "누군가와 말한다 (예: 노인에게 길을 묻는다, 부탁한다, 겁을 준다, 속인다)",
    "try": "무언가에 맞서거나 해 본다 (예: 문을 부순다, 자물쇠를 딴다, 덫을 피해 건너간다)",
    "declare": "자신에 대한 사실을 밝힌다 (예: 나는 이 마을 출신이다, 예전에 그와 함께 일했다)",
    "cut": "기다리거나 쉬며 시간을 보낸다 (예: 날이 밝을 때까지 기다린다, 잠깐 눈을 붙인다)",
    "choose": "갈림길에서 하나를 고른다 (예: 둘 중 하나를 택한다)",
    "end": "더 하는 것이 없다",
}
EN = {
    "step_q": {1: "What does the player's sentence try to do first?", 2: "What does it do next?",
               3: "What does it do after that?"},
    "step": {"go": "move somewhere", "look": "look at or read something to learn about it",
             "take": "pick something up", "give": "hand something to someone", "talk": "speak with someone",
             "try": "act on something to overcome or change it", "declare": "state a fact about oneself",
             "cut": "wait or rest to let time pass", "choose": "pick one option at a crossroads",
             "end": "nothing more"},
    "approach_q": "How does the player do it?",
    "approach": {"force": "pushing, breaking or enduring by strength", "finesse": "delicate hands, agility, stealth",
                 "wits": "observing, planning, tricks, distraction", "charm": "winning someone over by words or manner"},
    "strain_q": "In this scene, the action is…",
    "strain": {"natural": "doable without strain", "forced": "doable but reckless or overexerting",
               "impossible": "impossible in this scene"},
    "tone_q": "In what manner does the player speak?",
    "tone": {"polite": "asks or requests politely", "friendly": "chats warmly", "plead": "begs or appeals",
             "threaten": "intimidates or threatens", "deceive": "lies or deceives"},
    "intent_q": "Which of these does the player's sentence mean?",
    "target_q": "What is the player acting on?",
    "claim_q": "What false claim does the player make?",
    "rely_q": "What actually helps this attempt?",
    "rely_none": "nothing helps this attempt",
    "check": {"contradicts": "Does this sentence contradict the facts in the context?",
              "invents": "Does this sentence make up a person, thing or path that is not in the context?"},
    "yes": "yes", "no": "no",
}
# Layer-1 alternatives for sentences with more than one action.
COUNT_Q = "플레이어 문장은 서로 다른 행동을 몇 가지 차례로 합니까?"
COUNT = {"one": "한 가지 행동만 한다", "two": "두 가지 행동을 차례로 한다", "three": "세 가지 이상의 행동을 차례로 한다"}
NEXT_Q = {2: "첫 행동을 마친 뒤, 문장이 이어서 하는 다른 행동은 무엇입니까?",
          3: "두 번째 행동을 마친 뒤, 문장이 또 이어서 하는 다른 행동은 무엇입니까?"}
NEXT_END = "문장에 이어지는 다른 행동이 없다"
# Layer-1 wording round 2: first-action question and sharper examples for the confused schemas.
SELF = {"t_you": "당신 자신", "t_self": "자기 자신"}   # the no-target option named as the entity it is
COND_Q = "플레이어 문장에서 \"{a}\" 다음에 이어서 하는 행동은 무엇입니까?"
NTH_Q = {2: "플레이어 문장에서 두 번째로 하는 행동은 무엇입니까? 첫 행동은 보지 않습니다.",
         3: "플레이어 문장에서 세 번째로 하는 행동은 무엇입니까? 앞의 두 행동은 보지 않습니다."}
S1_V2 = "플레이어 문장에서 가장 먼저 하는 행동은 무엇입니까? 뒤에 이어지는 행동은 보지 않습니다."
ASK_V2 = {
    "go": "어딘가로 간다 (예: 북쪽 문으로 나간다, 위층으로 올라가자)",
    "look": "무언가를 살피거나 읽어 보며, 그것이 어떤지 알아본다 (예: 상자 안을 들여다본다, 여기 뭐가 있지?, 왜 안 열리지?)",
    "take": "무언가를 집는다 (예: 바닥의 칼을 줍는다)",
    "give": "누군가에게 무언가를 건넨다 (예: 문지기에게 동전을 쥐여 준다)",
    "talk": "누군가에게 묻거나, 부탁하거나, 겁을 주거나, 속이는 말을 한다 (예: 노인에게 길을 묻는다)",
    "try": "무언가를 이루려고 힘, 솜씨, 꾀, 말솜씨로 맞선다 (예: 문을 부순다, 자물쇠를 딴다, 돌을 던져 주의를 돌린다, "
           "성난 사람을 달래거나 설득해 마음을 돌린다, 혼자 몸을 단련한다)",
    "declare": "자신의 과거나 인연을 새로 밝히거나 떠올린다 (예: 나는 이 마을 출신이다, 그러고 보니 그는 내 옛 동료다)",
    "cut": "기다리거나 쉬며 시간을 보낸다 (예: 날이 밝을 때까지 기다린다, 잠깐 눈을 붙인다)",
    "choose": "어떻게 할지 결정을 내린다 (예: 보물은 마을에 돌려주기로 한다, 그를 범인으로 지목한다, 둘 중 하나를 택한다)",
}

# Round 3: round 2 with examples kept away from every bench and skeleton sentence.
ASK_V3 = {
    "go": "어딘가로 간다 (예: 북쪽 문으로 나간다, 위층으로 올라가자)",
    "look": "무언가를 살피거나 읽어 보며, 그것이 어떤지 알아본다 (예: 상자 안을 들여다본다, 저건 뭐지?)",
    "take": "무언가를 집는다 (예: 바닥의 칼을 줍는다)",
    "give": "누군가에게 무언가를 건넨다 (예: 문지기에게 동전을 쥐여 준다)",
    "talk": "누군가에게 묻거나, 부탁하거나, 겁을 주거나, 속이는 말을 한다 (예: 노인에게 길을 묻는다)",
    "try": "무언가를 이루려고 힘, 솜씨, 꾀, 말솜씨로 맞선다 (예: 벽을 부순다, 매듭을 푼다, 미끼로 주의를 끈다, "
           "적의를 품은 상대를 구슬려 마음을 돌린다, 몸을 단련한다)",
    "declare": "자신의 과거나 인연을 새로 밝히거나 떠올린다 (예: 나는 이 마을 출신이다, 그는 내 옛 스승이다)",
    "cut": "기다리거나 쉬며 시간을 보낸다 (예: 날이 밝을 때까지 기다린다, 잠깐 눈을 붙인다)",
    "choose": "어떻게 할지 결정을 내린다 (예: 남은 돈은 고아원에 맡기기로 한다, 두 길 중 강 쪽을 택한다)",
}

# Round 4 (malkuth): English questions over the round-3 options, English options, and a count that merges one goal.
Q_EN = {1: "What is the first action in the player's sentence? Ignore any action that follows it.",
        2: "What does the sentence do next?", 3: "What does it do after that?"}
COUNT_EN = ("How many different actions does the player's sentence take, one after another?",
            {"one": "just one action", "two": "two actions in turn", "three": "three or more actions in turn"})
COUNT_GOAL_EN = ("How many separate actions does the player's sentence take, one after another? Movements that serve "
                 "one goal, like kneeling and begging or wedging a bar and lifting, are one action.",
                 {"one": "just one action", "two": "two separate actions in turn",
                  "three": "three or more separate actions in turn"})
ASK_EN = {
    "go": "move somewhere (e.g. leave by the north gate, go upstairs)",
    "look": "look at or read something to learn about it (e.g. peer into a box, what is that?)",
    "take": "pick something up (e.g. pick the knife off the floor)",
    "give": "hand something to someone (e.g. slip the guard a coin)",
    "talk": "ask, request, threaten or lie to someone in words (e.g. ask an old man the way)",
    "try": "act to overcome or change something by strength, skill, wits or charm (e.g. break a wall, untie a knot, "
           "lure attention with bait, win over someone hostile, train one's body)",
    "declare": "reveal or recall a fact about one's own past or ties (e.g. I grew up in this town, he was my old teacher)",
    "cut": "wait or rest to let time pass (e.g. wait for dawn, take a nap)",
    "choose": "make a decision about what to do (e.g. leave the money to the orphanage, take the river road)",
}

# Round 5 (malkuth layer 2): sharper strain and tone, a claim question without a "no claim" option.
STRAIN_M3 = {"natural": "보통 사람이 해 볼 만하다 (예: 문을 걷어찬다, 돌을 던진다)",
             "forced": "할 수는 있지만 몸을 혹사하거나 크게 무리한다 (예: 맨손으로 뜨거운 쇠를 붙든다)",
             "impossible": "사람의 힘으로는 할 수 없거나 이 장면에 없는 것을 쓴다 (예: 눈빛만으로 문을 연다)"}
TONE_M3 = {"polite": "정중하게 묻거나 부탁한다", "friendly": "친근하게 수다를 떨거나 농담한다",
           "plead": "애원하거나 매달린다", "threaten": "겁을 주거나 위협한다",
           "deceive": "사실이 아닌 말로 속이거나 둘러댄다 (예: 자신을 다른 사람이라고 꾸며 댄다)"}
CLAIM_Q_M3 = "플레이어가 하는 거짓말은 다음 중 어느 것에 가장 가깝습니까?"

# The narration check as one choice instead of two yes/no questions.
CHECK_Q = "이 문장은 문맥과 비교해 어떻습니까?"
CHECK_OPTS = {"fine": "문맥의 사실과 맞고, 문맥에 없는 것을 지어내지 않았다",
              "contradicts": "문맥의 사실과 어긋난다",
              "invents": "문맥에 없는 사람, 물건, 길을 지어냈다"}


def choice(q, criteria):
    return {"type": "choice", "instructions": q, "criteria": criteria}


def keyed(options: dict, variant: str, family: str):
    """options: canonical key -> description. Returns (criteria, key map canonical -> criteria key)."""
    if variant == "ko_keys" and family in KO_KEYS:
        names = KO_KEYS[family]
        return {names[k]: d for k, d in options.items()}, {k: names[k] for k in options}
    if variant in ("ko_keys", "desc_only") or (variant == "names" and family in ("intent", "target", "rely")):
        return {d: None for d in options.values()}, {k: d for k, d in options.items()}
    if variant == "reverse":
        rev = dict(reversed(list(options.items())))
        return rev, {k: k for k in options}
    return dict(options), {k: k for k in options}


# ---------------------------------------------------------------- scene rendering (the engine's context frames)

def fill(t, **kw):
    return ko.fill(t, **kw)


def render(sc, text, lean=False):
    place = sc["place"]["name"]
    facts = []
    for h in sc.get("people", []):
        facts.append(fill(ko.FRAME["at_place"], x=h["name"], y=place))
    for t in sc.get("things", []):
        w = t["where"]
        if w == "here":
            facts.append(fill(ko.FRAME["at_place"], x=t["name"], y=place))
        else:
            facts.append(fill(ko.FRAME["at_agent"], x=t["name"], y="당신" if w == "player" else w))
    for o in sc.get("obstacles", []):
        facts.append(fill(ko.FRAME["at_place"], x=o["name"], y=place))
    facts.append(f"당신은 {place}에 있습니다")
    for o in sc.get("obstacles", []):
        facts.append(f"{o['name']}: {o.get('fill', 0)}/{o.get('boxes', 1)}")
    for w in sc.get("threats", []):
        facts.append(f"{w}: 0/4")
    if not lean:
        for e in sc.get("exits", []):
            facts.append(fill(ko.FRAME["link"], p=place, q=e))
            facts.append(fill(ko.FRAME["link"], p=e, q=place))
        for h in sc.get("people", []):
            facts.append(fill("{h}{은} 당신을 ", h=h["name"]) + ko.TRUST_VERBS[h.get("trust", 0)])
        pl = sc.get("player", {})
        for k, v in pl.get("stats", {}).items():
            facts.append(f"당신의 {ko.APPROACHES[k]}: {v}")
        for t in pl.get("traits", []):
            facts.append(f"당신의 특성: {t['name']}")
        facts.append("당신의 상처: 0")
    memory = [fill(ko.FRAME["memory"], label=m) for m in sc.get("memory", [])]
    public = [fill(ko.FRAME["senses"], x=place, text=", ".join(sc["place"].get("senses", [])))]
    for h in sc.get("people", []):
        for k, f in (("voice", "voice"), ("desire", "desire"), ("fear", "fear_of")):
            if h.get(k):
                public.append(fill(ko.FRAME[f], x=h["name"], text=h[k]))
        if h.get("topics"):
            public.append(fill(ko.FRAME["topics"], x=h["name"], text=", ".join(h["topics"])))
        if h.get("wants"):
            public.append(fill(ko.FRAME["wants"], x=h["name"], text=", ".join(h["wants"])))
    for x in sc.get("things", []) + sc.get("obstacles", []):
        if x.get("look"):
            public.append(fill(ko.FRAME["look"], x=x["name"], text=x["look"]))
    out = []
    for head, lines in ((ko.SECTIONS["fact"], facts), (ko.SECTIONS["memory"], memory), (ko.SECTIONS["public"], public)):
        if lines:
            out += [head] + [f"- {x}" for x in lines]
    return "\n".join(out) + "\n\n" + sentence(text)


def sentence(text):
    return f"플레이어 문장: {text}"


# ---------------------------------------------------------------- what the scene offers

def available(sc):
    have = {"look", "try", "cut"}
    if sc.get("exits"):
        have.add("go")
    if any(t["where"] == "here" for t in sc.get("things", [])):
        have.add("take")
    if sc.get("people"):
        have.add("talk")
        if any(t["where"] == "player" for t in sc.get("things", [])):
            have.add("give")
    if sc.get("latents"):
        have.add("declare")
    if sc.get("forks"):
        have.add("choose")
    return [s for s in SAY if s in have]


def intents(sc, schema):
    """canonical key -> engine action label, for one schema's intent question."""
    place = sc["place"]["name"]
    out = {}
    if schema == "go":
        for e in sc.get("exits", []):
            out[f"go:{e}"] = fill(ko.ACTION["go"], q=e)
    elif schema == "look":
        for x in [place] + [h["name"] for h in sc.get("people", [])] + [t["name"] for t in sc.get("things", [])
                  if t["where"] in ("here", "player")] + [o["name"] for o in sc.get("obstacles", [])] + sc.get("threats", []):
            out[f"look:{x}"] = fill(ko.ACTION["look"], x=x)
    elif schema == "take":
        for t in sc.get("things", []):
            if t["where"] == "here":
                out[f"take:{t['name']}"] = fill(ko.ACTION["take"], x=t["name"])
    elif schema == "give":
        for t in sc.get("things", []):
            if t["where"] == "player":
                for h in sc.get("people", []):
                    out[f"give:{t['name']}:{h['name']}"] = fill(ko.ACTION["give"], h=h["name"], x=t["name"])
    elif schema == "talk":
        for h in sc.get("people", []):
            for tp in h.get("topics", []):
                out[f"talk:{h['name']}:{tp}"] = fill(ko.ACTION["talk"], h=h["name"], title=tp)
            if h.get("favor"):
                out[f"talk:{h['name']}:favor"] = fill(ko.ACTION["favor"], h=h["name"], label=h["favor"])
            out[f"talk:{h['name']}:chat"] = fill(ko.ACTION["chat"], h=h["name"])
    elif schema == "declare":
        for lt in sc.get("latents", []):
            out[f"declare:{lt['name']}"] = fill(ko.ACTION["declare"], name=lt["name"])
    elif schema == "cut":
        out["cut:pass"] = ko.ACTION["pass"]
        if sc["place"].get("rest"):
            out["cut:rest"] = ko.ACTION["rest"]
    elif schema == "choose":
        for f in sc.get("forks", []):
            for c in f["options"]:
                out[f"choose:{f['name']}:{c}"] = c
    return out


def gold_intent(schema, d):
    return {"go": lambda: f"go:{d['to']}", "look": lambda: f"look:{d['at']}", "take": lambda: f"take:{d['thing']}",
            "give": lambda: f"give:{d['thing']}:{d['to']}", "talk": lambda: f"talk:{d['to']}:{d['topic']}",
            "declare": lambda: f"declare:{d['latent']}", "cut": lambda: f"cut:{d['kind']}",
            "choose": lambda: f"choose:{d['fork']}:{d['option']}"}[schema]()


def opaque(options: dict) -> tuple[dict, dict]:
    """The engine keys intents by story ids the model cannot read as Korean; stand in with e1, e2, …"""
    ids = {k: f"e{i + 1}" for i, k in enumerate(options)}
    return {ids[k]: v for k, v in options.items()}, ids


# ---------------------------------------------------------------- requests per item and variant

def layer1(item, variant):
    sc, text = item["scene"], item["text"]
    steps = item["gold"]["steps"]
    if variant in ("v4a", "v4b", "v4c"):
        ask = ASK_EN if variant == "v4b" else ASK_V3
        first = {s: ask[s] for s in available(sc)}
        later = {s: ask[s] for s in SAY}
        qs, golds = {}, {}
        for i, opts in ((1, first), (2, later), (3, later)):
            if i == 3 and len(steps) < 2:
                continue
            qs[f"s{i}"] = choice(Q_EN[i] if variant != "v4c" else (S1_V2 if i == 1 else OLD_STEP_QUESTION[i]), opts)
            golds[f"s{i}"] = (steps[i - 1] if i <= len(steps) else None, {k: k for k in opts})
        cq, co = COUNT_GOAL_EN if variant == "v4c" else COUNT_EN
        qs["n"] = choice(cq, co)
        golds["n"] = (("one", "two", "three")[min(len(steps), 3) - 1], {k: k for k in co})
        return sentence(text), qs, golds
    if variant in ("v2", "v3", "v3en", "v5", "cond"):
        ask = ASK_V2 if variant == "v2" else ASK_V3
        first = {s: ask[s] for s in available(sc)}
        later = {s: ask[s] for s in SAY}
        qs, golds = {}, {}
        for i, opts in ((1, first), (2, later), (3, later)):
            if i == 3 and len(steps) < 2:
                continue
            if variant == "cond" and i > 1:
                # the step before, as the engine would know it once that step is read (gold here: a later step
                # only counts when the earlier ones are right)
                before = ask[steps[i - 2]].split(" (")[0] if i - 2 < len(steps) else None
                q = COND_Q.format(a=before) if before else OLD_STEP_QUESTION[i]
            else:
                q = S1_V2 if i == 1 else NTH_Q[i] if variant == "v5" else OLD_STEP_QUESTION[i]
            qs[f"s{i}"] = choice(q, opts)
            g = steps[i - 1] if i <= len(steps) else None
            golds[f"s{i}"] = (g, {k: k for k in opts})
        qs["n"] = choice("How many different actions does the player's sentence take, one after another?",
                         {"one": "just one action", "two": "two actions in turn", "three": "three or more actions in turn"}) \
            if variant == "v3en" else choice(COUNT_Q, COUNT)
        golds["n"] = (("one", "two", "three")[min(len(steps), 3) - 1], {k: k for k in COUNT})
        return sentence(text), qs, golds
    first = {s: (EXAMPLES if variant in ("examples", "combo") else EN["step"] if variant == "en" else ko.SCHEMA_DESC)[s]
             for s in available(sc)}
    later = {s: (EXAMPLES if variant in ("examples", "combo") else EN["step"] if variant == "en" else ko.SCHEMA_DESC)[s]
             for s in SAY}
    later["end"] = EXAMPLES["end"] if variant in ("examples", "combo") else EN["step"]["end"] if variant == "en" else \
        NEXT_END if variant == "next_q" else OLD_END
    if variant in ("count", "combo"):
        del later["end"]
    qs, golds = {}, {}
    for i, opts in ((1, first), (2, later), (3, later)):
        if i == 3 and len(steps) < 2:
            continue
        crit, km = keyed(opts, variant, "step")
        q = EN["step_q"][i] if variant == "en" else NEXT_Q[i] if variant == "next_q" and i > 1 else \
            OLD_STEP_QUESTION[i]
        qs[f"s{i}"] = choice(q, crit)
        g = steps[i - 1] if i <= len(steps) else "end"
        golds[f"s{i}"] = (km[g] if g in km else None, km)
    if variant in ("count", "combo"):
        qs["n"] = choice(COUNT_Q, COUNT)
        golds["n"] = (("one", "two", "three")[min(len(steps), 3) - 1], {k: k for k in COUNT})
    state = sentence(text)
    if variant == "scene_ctx":
        names = [h["name"] for h in sc.get("people", [])] + [t["name"] for t in sc.get("things", [])] + \
                [o["name"] for o in sc.get("obstacles", [])]
        state = f"장면: {sc['place']['name']}, " + ", ".join(names) + "\n" + state
    return state, qs, golds


def layer2(item, variant):
    sc, text, g = item["scene"], item["text"], item["gold"]
    schema, d = g["steps"][0], g["detail"]
    state = sentence(text) if variant == "no_ctx" else render(sc, text, lean=variant == "lean_ctx")
    qs, golds = {}, {}
    en = variant == "en"
    if variant in ("m2", "m3"):
        en_fams = {"target", "approach"}
    else:
        en_fams = {"target", "approach", "intent", "strain", "tone", "claim"} if en else set()

    def add(fam, q, opts, gold):
        if gold not in opts:
            return
        if fam in ("intent", "target") and variant not in ("ko_keys", "desc_only", "names"):
            crit, ids = opaque(opts)
            km = ids
            if variant == "reverse" or (variant in ("m2", "m3") and fam == "intent"):
                crit = dict(reversed(list(crit.items())))
        else:
            crit, km = keyed(opts, variant, fam)
        qs[fam] = choice(q, crit)
        golds[fam] = (km[gold], km)

    if schema == "try":
        targets = {o["name"]: o["name"] for o in sc.get("obstacles", [])}
        targets |= {h["name"]: h["name"] for h in sc.get("people", [])}
        targets |= {t["name"]: t["name"] for t in sc.get("things", []) if t["where"] in ("here", "player")}
        targets |= {w: w for w in sc.get("threats", [])}
        targets["player"] = SELF.get(variant, ko.NO_TARGET)
        if len(targets) > 1:
            add("target", EN["target_q"] if "target" in en_fams else ko.SLOT_QUESTION["target"], targets, d["target"])
        if d["strain"] != "impossible":          # the engine refuses it before the approach matters
            add("approach", EN["approach_q"] if "approach" in en_fams else ko.SLOT_QUESTION["approach"],
                EN["approach"] if "approach" in en_fams else ko.APPROACH_DESC, d["approach"])
        add("strain", EN["strain_q"] if en else ko.SLOT_QUESTION["strain"],
            EN["strain"] if en else STRAIN_M3 if variant == "m3" else ko.STRAIN_DESC, d["strain"])
    else:
        opts = intents(sc, schema)
        if len(opts) > 1:
            add("intent", EN["intent_q"] if en else ko.SLOT_QUESTION["intent"], opts, gold_intent(schema, d))
        if schema == "talk":
            add("tone", EN["tone_q"] if en else ko.SLOT_QUESTION["tone"],
                EN["tone"] if en else TONE_M3 if variant == "m3" else ko.TONE_DESC, d["tone"])
            if d.get("tone") == "deceive" and sc.get("claims"):
                if variant == "m3":
                    copts = {**{c: c for c in sc["claims"]}, "other": "위의 어느 것과도 다른 거짓말"}
                    add("claim", CLAIM_Q_M3, copts, d.get("claim") or "other")
                else:
                    copts = {"none": OLD_NO_CLAIM, **{c: c for c in sc["claims"]}}
                    add("claim", EN["claim_q"] if en else OLD_CLAIM_Q, copts, d.get("claim") or "none")
    return state, qs, golds


def rely_req(item, variant):
    a = item["attempt"]
    lines = [f"시도: {a['label']}"]
    if a["target"].get("look"):
        lines.append(fill(ko.FRAME["look"], x=a["target"]["name"], text=a["target"]["look"]))
    if item.get("text"):
        lines.append(sentence(item["text"]))
    state = "\n".join(lines)
    descs = []
    for o in item["options"]:
        k = o["kind"]
        name = o.get("name") or ""
        descs.append(ko.fill(ko.RELY_DESC[k], name=name, text=o.get("text") or ""))
    if variant == "noul":
        qs = {f"r{i}": {"type": "noul", "instructions": f"다음이 이 시도를 실제로 돕습니까? {d}",
                        "criteria": {"true": OLD_YES, "false": OLD_NO}} for i, d in enumerate(descs)}
        return state, qs
    opts = {f"r{i}": d for i, d in enumerate(descs)}
    if variant == "names":
        crit = {d: None for d in descs}
        crit[ko.RELY_NONE] = None
        return state, {"rely": choice(ko.RELY_QUESTION, crit)}
    if variant == "en":
        return state, {"rely": choice(EN["rely_q"], {**opts, "none": EN["rely_none"]})}
    if variant == "reverse":
        return state, {"rely": choice(ko.RELY_QUESTION, dict(reversed(list({**opts, "none": ko.RELY_NONE}.items()))))}
    return state, {"rely": choice(ko.RELY_QUESTION, {**opts, "none": ko.RELY_NONE})}


def check_req(item, variant):
    lines = [ko.SECTIONS["fact"]] + [f"- {x}" for x in item["facts"]]
    if item.get("public"):
        lines += [ko.SECTIONS["public"]] + [f"- {x}" for x in item["public"]]
    state = "\n".join(lines)
    if item.get("happened"):
        state += "\n" + ko.HEAD["happened"] + "\n" + "\n".join(f"- {x}" for x in item["happened"])
    s = item["sentence"]
    qs = {}
    if variant == "check_choice":
        return state, {"check": choice(f"{CHECK_Q}\n문장: {s}", CHECK_OPTS)}
    if variant == "check_en":
        return state, {"check": choice(f"Compared with the context, this sentence…\nSentence: {s}",
                                       {"fine": "agrees with the facts and makes nothing up",
                                        "contradicts": "contradicts a fact in the context",
                                        "invents": "makes up a person, thing or path not in the context"})}
    for k, q in OLD_CHECK.items():
        if variant == "en":
            qs[k] = {"type": "noul", "instructions": f"{EN['check'][k]}\nSentence: {s}",
                     "criteria": {"true": EN["yes"], "false": EN["no"]}}
        elif variant == "sent_state":
            qs[k] = {"type": "noul", "instructions": q, "criteria": {"true": OLD_YES, "false": OLD_NO}}
        else:
            qs[k] = {"type": "noul", "instructions": f"{q}\n문장: {s}", "criteria": {"true": OLD_YES, "false": OLD_NO}}
    if variant == "sent_state":
        state += "\n[문장]\n" + s
    return state, qs


VARIANTS = {
    # name: families it changes (others fall back to base, so each family compares like with like)
    "base": None,
    "ko_keys": {"step", "intent", "target", "approach", "strain", "tone"},
    "desc_only": {"step", "intent", "target", "approach", "strain", "tone"},
    "examples": {"step"},
    "en": {"step", "intent", "target", "approach", "strain", "tone", "claim", "rely", "check"},
    "scene_ctx": {"step"},
    "lean_ctx": {"intent", "target", "approach", "strain", "tone", "claim"},
    "no_ctx": {"intent", "target", "approach", "strain", "tone", "claim"},
    "reverse": {"step", "intent", "target", "approach", "strain", "tone", "rely"},
    "names": {"rely"},
    "noul": {"rely"},
    "sent_state": {"check"},
    "perm3": {"step", "intent", "target", "approach", "strain", "tone", "rely"},
    "count": {"step"},
    "next_q": {"step"},
    "check_choice": {"check"},
    "combo": {"step"},          # examples + count
    "v2": {"step"},             # combo with the round-2 wording
    "v3": {"step"},             # v2 with examples that echo no test sentence
    "m2": {"intent", "target", "approach", "strain", "tone", "claim"},   # malkuth's best per family
    "check_en": {"check"},
    "v3en": {"step"},           # v3 with the count asked in English
    "v4a": {"step"},            # v3 options, English questions
    "v4b": {"step"},            # English options and questions
    "v4c": {"step"},            # v3 with a count that merges one goal, in English
    "v5": {"step"},             # v3 with later steps asked by number, like the first
    "cond": {"step"},           # v3 with each later step asked after the step before it, by name
    "t_you": {"target"},
    "t_self": {"target"},
    "m3": {"intent", "target", "approach", "strain", "tone", "claim"},   # m2 with sharper strain, tone, claim
}


# ---------------------------------------------------------------- running

def permuted(qs):
    """Each choice question three times in one request, under three option orders; the state is computed once."""
    out = {}
    for k, q in qs.items():
        if q["type"] != "choice":
            out[k] = q
            continue
        keys = list(q["criteria"])
        for i, order in enumerate((keys, keys[::-1], keys[1::2] + keys[0::2])):
            out[f"{k}#{i}"] = {**q, "criteria": {x: q["criteria"][x] for x in order}}
    return out


async def decide(client, url, state, qs, perm=False):
    t = time.perf_counter()
    sent = permuted(qs) if perm else qs
    r = await client.post(f"{url}/v1/systemone", json={"state": state, "model": "kev-latest", "questions": sent})
    r.raise_for_status()
    ms = (time.perf_counter() - t) * 1000
    raw = {}
    for k, a in r.json()["answers"].items():
        raw[k] = {"true": a["noul"], "false": 1 - a["noul"]} if a["type"] == "noul" else a["probabilities"]
    out = {}
    for k in qs:
        parts = [v for kk, v in raw.items() if kk.split("#")[0] == k]
        out[k] = {o: sum(p[o] for p in parts) / len(parts) for o in parts[0]}
    return out, ms


def load(only=None):
    items = []
    for f in sorted((ROOT / "data").glob("*.jsonl")):
        if only and f.stem not in only:
            continue
        items += [json.loads(line) for line in f.read_text().splitlines() if line.strip()]
    return items


def blank(it):
    """The item with its sentence emptied: the model's prior over the same options in the same context."""
    it = dict(it)
    if it["kind"] == "sentence":
        it["text"] = ""
    elif it["kind"] == "rely":
        it["text"] = None
    else:
        it["sentence"] = ""
    return it


async def run(model, variants, url, only, prior=False):
    items = load(only)
    if prior:
        items = [blank(it) for it in items]
    out_dir = RUNS / "results" / model
    out_dir.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=120) as client:
        info = (await client.get(f"{url}/v1/models")).json()["models"][0]["run"]
        print(f"{model}: server runs {info}; {len(items)} items")
        for v in variants:
            rows, t0 = [], time.time()
            changed = VARIANTS[v]

            def skip(fams):
                return changed is not None and not (changed & fams)
            for it in items:
                if it["kind"] == "sentence":
                    for layer, fams in ((layer1, {"step"}), (layer2, {"intent", "target", "approach", "strain", "tone",
                                                                      "claim"})):
                        if skip(fams):
                            continue
                        state, qs, golds = layer(it, v)
                        if not qs:
                            continue
                        ans, ms = await decide(client, url, state, qs, perm=v == "perm3")
                        for k, (g, km) in golds.items():
                            fam = "step" if k == "n" or (k.startswith("s") and k[1:].isdigit()) else k
                            rows.append({"id": it["id"], "genre": it["genre"], "family": fam, "q": k, "gold": g,
                                         "probs": ans[k], "ms": ms, "n_q": len(qs)})
                elif it["kind"] == "rely" and not skip({"rely"}):
                    state, qs = rely_req(it, v)
                    ans, ms = await decide(client, url, state, qs, perm=v == "perm3")
                    descs = [ko.fill(ko.RELY_DESC[o["kind"]], name=o.get("name") or "", text=o.get("text") or "")
                             for o in it["options"]]
                    if v == "noul":
                        p = {f"r{i}": ans[f"r{i}"]["true"] for i in range(len(descs))}
                    elif v == "names":
                        p = {f"r{i}": ans["rely"].get(d, 0.0) for i, d in enumerate(descs)}
                    else:
                        p = {f"r{i}": ans["rely"].get(f"r{i}", 0.0) for i in range(len(descs))}
                    rows.append({"id": it["id"], "genre": it["genre"], "family": "rely", "q": "rely",
                                 "gold": sorted(it["relevant"]), "probs": p, "ms": ms, "n_q": len(qs),
                                 "per_option": v == "noul"})
                elif it["kind"] == "check" and not skip({"check"}):
                    state, qs = check_req(it, v)
                    ans, ms = await decide(client, url, state, qs, perm=v == "perm3")
                    if v in ("check_choice", "check_en"):
                        # each flag is the share of its option; "bad" is anything but fine, which is what the
                        # engine acts on (a rewrite)
                        p = ans["check"]
                        for k, pk in (("contradicts", p["contradicts"]), ("invents", p["invents"]),
                                      ("bad", 1 - p["fine"])):
                            gold = it["contradicts"] or it["invents"] if k == "bad" else it[k]
                            rows.append({"id": it["id"], "genre": it["genre"], "family": "check", "q": k,
                                         "gold": "true" if gold else "false", "probs": {"true": pk, "false": 1 - pk},
                                         "ms": ms, "n_q": 1})
                        continue
                    for k in qs:
                        rows.append({"id": it["id"], "genre": it["genre"], "family": "check", "q": k,
                                     "gold": "true" if it[k] else "false", "probs": ans[k], "ms": ms, "n_q": len(qs)})
            (out_dir / f"{v}{'.prior' if prior else ''}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
            print(f"  {v}: {len(rows)} answers in {time.time() - t0:.0f}s")


# ---------------------------------------------------------------- scoring

def metrics(rows):
    if not rows:
        return None
    n = len(rows)
    acc = sum(max(r["probs"], key=r["probs"].get) == r["gold"] for r in rows) / n
    brier = sum(sum((p - (k == r["gold"])) ** 2 for k, p in r["probs"].items()) for r in rows) / n
    acc_rows = [r for r in rows if max(r["probs"].values()) >= THETA]
    cover = len(acc_rows) / n
    wrong = sum(max(r["probs"], key=r["probs"].get) != r["gold"] for r in acc_rows) / max(1, len(acc_rows))
    return {"n": n, "acc": acc, "brier": brier, "cover": cover, "err_acc": wrong}


def rely_metrics(rows, share=RELY_SHARE):
    exact = prec_n = prec_d = rec_n = rec_d = 0
    for r in rows:
        cut = 0.5 if r.get("per_option") else share
        kept = {int(k[1:]) for k, p in r["probs"].items() if p >= cut}
        gold = set(r["gold"])
        exact += kept == gold
        prec_n += len(kept & gold); prec_d += len(kept)
        rec_n += len(kept & gold); rec_d += len(gold)
    n = len(rows)
    return {"n": n, "exact": exact / n, "precision": prec_n / max(1, prec_d), "recall": rec_n / max(1, rec_d)}


def score(models, by):
    res = RUNS / "results"
    models = models or sorted(p.name for p in res.iterdir() if p.is_dir())
    fams = ("step", "intent", "target", "approach", "strain", "tone", "claim", "check")
    for m in models:
        print(f"\n## {m}")
        print("| variant | " + " | ".join(fams) + " | rely exact (P/R) | ms/call |")
        print("|---|" + "---|" * (len(fams) + 2))
        for f in sorted((res / m).glob("*.jsonl"), key=lambda p: (p.stem != "base", p.stem)):
            rows = [json.loads(x) for x in f.read_text().splitlines()]
            v = f.stem
            changed = VARIANTS.get(v)
            cells = []
            for fam in fams:
                if changed is not None and fam not in changed:
                    cells.append("·")
                    continue
                mm = metrics([r for r in rows if r["family"] == fam])
                cells.append(f"{mm['acc']:.3f} ({mm['n']})" if mm else "-")
            rr = [r for r in rows if r["family"] == "rely"]
            rely = rely_metrics(rr) if rr and (changed is None or "rely" in changed) else None
            calls = {}
            for r in rows:
                calls[(r["id"], r["family"] in ("step",))] = r["ms"]
            ms = sum(calls.values()) / max(1, len(calls))
            rc = f"{rely['exact']:.3f} ({rely['precision']:.2f}/{rely['recall']:.2f})" if rely else "·"
            print(f"| {v} | " + " | ".join(cells) + f" | {rc} | {ms:.0f} |")
        if by:
            base = [json.loads(x) for x in (res / m / "base.jsonl").read_text().splitlines()]
            genres = sorted({r["genre"] for r in base})
            print(f"\n{m} base by genre (step acc / check acc):")
            for g in genres:
                s = metrics([r for r in base if r["genre"] == g and r["family"] == "step"])
                c = metrics([r for r in base if r["genre"] == g and r["family"] == "check"])
                print(f"  {g}: step {s['acc']:.3f} ({s['n']})  check {c['acc']:.3f}" if s and c else f"  {g}: -")


def validate(only):
    bad = 0
    for it in load(only):
        if it["kind"] != "sentence":
            continue
        sc, g = it["scene"], it["gold"]
        s0, d = g["steps"][0], g["detail"]
        probs = []
        if s0 not in available(sc):
            probs.append(f"first step {s0} not available")
        if s0 == "try":
            names = {o["name"] for o in sc.get("obstacles", [])} | {h["name"] for h in sc.get("people", [])} | \
                    {t["name"] for t in sc.get("things", []) if t["where"] in ("here", "player")} | set(sc.get("threats", [])) | {"player"}
            if d.get("target") not in names:
                probs.append(f"target {d.get('target')!r} not in scene")
        else:
            try:
                key = gold_intent(s0, d)
            except KeyError as e:
                probs.append(f"detail missing {e}")
                key = None
            if key and key not in intents(sc, s0):
                probs.append(f"intent {key!r} not among {list(intents(sc, s0))}")
        for st in g["steps"]:
            if st not in SAY:
                probs.append(f"unknown step {st}")
        if probs:
            bad += 1
            print(it["id"], "|", it["text"], "|", "; ".join(probs))
    print("problems:", bad)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("model")
    r.add_argument("--variants", default=",".join(VARIANTS))
    r.add_argument("--url", default="http://127.0.0.1:8081")
    r.add_argument("--only", default="")
    r.add_argument("--prior", action="store_true")
    vv = sub.add_parser("validate")
    vv.add_argument("--only", default="")
    s = sub.add_parser("score")
    s.add_argument("--models", default="")
    s.add_argument("--by", action="store_true")
    a = ap.parse_args()
    if a.cmd == "validate":
        validate(set(filter(None, a.only.split(","))))
    elif a.cmd == "run":
        asyncio.run(run(a.model, a.variants.split(","), a.url, set(filter(None, a.only.split(","))), a.prior))
    else:
        score(list(filter(None, a.models.split(","))), a.by)


if __name__ == "__main__":
    main()
