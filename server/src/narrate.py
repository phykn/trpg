import re
from difflib import SequenceMatcher

MEANING = 0.5
ADDED = 0.15
QUIET = 0.5
REWRITES = 2
MAX_SENTENCES = {"answer": 3, "scene": 4, "ending": 8, "dm": 3}
MAX_TOKENS = {"answer": 200, "scene": 300, "ending": 700, "dm": 200}
# Kanana's meaning check passes answers that drop the line (qa/findings.md); the share of each line's Hangul
# syllables found in the answer catches them. On the AI testers' games (qa_test/runs/qa-1 to qa-6) answers that kept
# their lines scored 0.69 and up, answers that dropped or bent one 0.44 and below.
COVER = 0.5
# An answer this close to one the person already gave says the same thing again; gemma4 did so even when told not to.
REPEAT = 0.8
# Words of the prompt itself; a text that names them is talking about its instructions, not to the player.
PROMPT_WORDS = ("할 말", "받은 것", "지침", "지킬 것", "질문자", "신상", "그릴 기척", "지켜본 일", "앞서 나눈 말")
# The narrator and the DM speak 합니다체 (CLAUDE.md); quoted speech inside a scene keeps its own.
HAEYO = re.compile(r"(세요|어요|아요|해요|예요|에요|죠|군요|네요)[.?!…~]*(\s|$)")
# The DM shows a sign instead of advising (game/07 2절); these endings tell the player what to do.
PUSH = re.compile(r"권(합니다|해 드립니다|하고 싶습니다)|(보|가|해|물어|살펴|둘러|찾아|내밀어|따져)\s?보(십시오|세요|시죠|시길|길)|"
                  r"(좋|낫)겠습니다|어떻습니까|어떨까|볼 만합니다|하십시오|가십시오|필요해 보입니다")
QUOTED = re.compile(r"\"[^\"]*\"|“[^”]*”|'[^']*'|‘[^’]*’")
REASONS = {"added": "받은 것에 없는 사람, 물건, 때, 곳을 더했다", "meaning": "할 말의 뜻이 빠졌거나 바뀌었다",
           "quiet": "말하지 않아야 할 내용을 말했다", "length": "너무 길다",
           "prompt": "지시문을 두고 말했다. 인물이나 진행자의 말만 쓴다",
           "style": "해요체로 썼다. 문장을 모두 '-습니다', '-ㅂ니까'로 맺는다",
           "push": "플레이어에게 할 일을 권했다. 권하지 말고 소리, 빛, 냄새, 몸짓 같은 기척만 그린다",
           "speech": "인물의 대사를 지어냈다. 따옴표 없이 몸짓만 그린다",
           "repeat": "앞서 한 대답을 되풀이했다. 플레이어가 방금 한 말에 맞춰 다르게 받아친다"}


class Narrator:
    def __init__(self, llm, decision):
        self.llm = llm
        self.decision = decision

    async def write(self, job):
        messages = make_messages(job)
        text = ""
        async for chunk in self.llm.stream(messages, MAX_TOKENS[job["kind"]]):
            text += chunk
            yield {"type": "delta", "text": chunk}
        checks = []
        for attempt in range(REWRITES + 1):
            failed, probs = await self.check(job, text)
            checks.append({"text": text, "failed": failed, "probs": probs})
            if not failed or attempt == REWRITES:
                break
            note = "이 글은 " + ", ".join(REASONS[f] for f in failed) + ". 지킬 것을 지켜 다시 쓴다."
            messages = [*messages, {"role": "assistant", "content": text}, {"role": "user", "content": note}]
            text = "".join([chunk async for chunk in self.llm.stream(messages, MAX_TOKENS[job["kind"]])])
            yield {"type": "replace", "text": text}
        yield {"type": "result", "text": text, "checks": checks}

    async def check(self, job, text):
        state = "받은 것:\n" + "\n".join(list_given(job)) + f"\n\n쓴 글:\n{text}"
        answers = await self.decision.decide(state, make_checks(job))
        return judge(job, answers, text)


def make_messages(job):
    given = "\n".join(g for g in list_given(job) if not g.startswith("플레이어의 말"))
    head, rules, user = {"dm": make_dm_prompt, "answer": make_answer_prompt}.get(job["kind"], make_scene_prompt)(job)
    system = f"{head}\n\n받은 것:\n{given}\n\n지킬 것:\n" + "\n".join(f"- {r}" for r in rules)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def list_given(job):
    if job["kind"] == "dm":
        return list_dm_given(job)
    if job["kind"] == "answer":
        given = [f"신상: {job['bio']}", f"태도: {job['attitude']}"]
        given += [f"곳과 때: {job['where']}"] if job.get("where") else []
        if job.get("recent"):
            given.append("앞서 나눈 말:\n" + "\n".join(f"  플레이어: {r['said'] or '(말없이 기다렸다)'}\n  {job['person']}: {r['answer']}"
                                                   for r in job["recent"]))
        given += [f"이미 한 말: {' / '.join(job['told'])}"] if job.get("told") else []
        given += [f"지켜본 일(플레이어가 한 일): {' / '.join(job['saw'])}"] if job.get("saw") else []
        return given + [f"할 말: {' / '.join(job['says']) or '없다'}", f"플레이어의 말: {job['said'] or '없다'}"]
    given = [f"도입: {job['intro']}"] if job.get("intro") else []
    given += [f"시각: {job['time']}"] if job.get("time") else []
    if job.get("place"):
        given.append(f"곳: {job['place']}" + (f". 모습: {job['desc']}" if job.get("desc") else ""))
    given += [f"이번에 적힌 것: {', '.join(job['written'])}"] if job.get("written") else []
    if job.get("happening"):
        given.append(f"{'당신이 없는 곳에서 그 사이 벌어진 일' if job.get('far') else '일어난 일'}: {' '.join(job['happening'])}")
    given += [f"이곳의 사람: {', '.join(job['people'])}"] if job.get("people") else []
    given += [f"플레이어의 결론: {job['answers']}"] if job.get("answers") else []
    return given


def list_dm_given(job):
    given = [f"상황: {job['situation']}"]
    given += [f"도입: {job['intro']}"] if job["intro"] else []
    given += [f"시각: {job['time']}"] if job["time"] else []
    given += [f"이곳: {job['here']}"] if job["here"] else []
    if job["person"]:
        person = job["person"]
        given.append(f"인물: {person['name']}. 신상: {person['bio']} 플레이어를 대하는 태도: {person['attitude']}")
    given += [f"가 보지 않은 곳: {job['far']}"] if job["far"] else []
    return given + [f"그릴 기척: {job['cue']}"]


def make_dm_prompt(job):
    rules = ["플레이어를 \"당신\"이라 부르고 합니다체로 한두 문장만 쓴다. '-세요', '-군요' 같은 해요체는 쓰지 않는다.",
             "플레이어를 이름이나 3인칭으로 부르지 않는다.",
             ("진행자는 세계의 기척을 보여 줄 뿐이고, 무엇을 할지는 플레이어가 고른다. 가 보라, 물어보라, 살펴보라처럼 "
              "권하거나 시키지 않는다." if job["key"] != "conclude" else "결론을 들려 달라는 말만 직접 한다."),
             "지어내는 것은 소리, 빛, 냄새, 몸짓뿐이다. 받은 것에 없는 사람, 물건, 흔적, 벌어진 일은 더하지 않는다.",
             "인물의 몸짓은 신상과 태도에서만 짐작한다. 사건의 진실, 단서, 누가 거짓말하는지는 말하지 않는다.",
             "인물의 대사를 지어내지 않는다. 따옴표를 쓰지 않는다.",
             "화면, 단추, 누르는 법은 말하지 않는다.",
             "신상이 플레이어를 이름으로 가리켜도 플레이어는 \"당신\"이라 부른다.",
             "한 문단으로 쓴다."]
    return "당신은 추리 TRPG 판을 이끄는 진행자(DM)다.", rules, "진행자로서 한마디 한다."


def make_answer_prompt(job):
    rules = [f"{job['person']}의 대사만 쓴다. 할 말 하나에 한두 문장이다. 이름, 따옴표, 설명은 붙이지 않는다.",
             "신상의 말투를 따르되 문법에 맞는 한국어로 쓰고, 태도에 맞게 플레이어의 말을 받아친다.",
             "플레이어는 지금 마주 보고 말을 건 사람이다. 플레이어에게 직접 말하고, '저 사람', '얘'처럼 남을 가리키듯 부르지 않는다.",
             "할 말이 있으면 그 내용을 빠짐없이 말한다. 태도는 말투에만 드러내고, 모른다고 하거나 피하지 않는다.",
             "할 말의 뜻을 바꾸지 않는다. 할 말에 없는 사람, 물건, 때, 곳을 더하지 않는다.",
             ("할 말이 없거나 답할 것이 없으면 플레이어의 말 자체에 신상대로 반응한다. 부탁이면 들어주거나 거절하고, "
              "넋두리나 농담이면 맞장구치거나 핀잔하고, 다그치면 발끈하거나 움츠러든다. 사건에 관한 것은 지어내지 않는다."),
             "앞서 나눈 말이 있으면 그 흐름을 이어 받고, 앞서 한 대답을 같은 말로 되풀이하지 않는다.",
             "이미 한 말을 다시 물으면 아까 말했다는 투로 짧게 다시 말한다.",
             "지켜본 일이 있으면 그 일을 보고 한마디 얹는다. 곳과 때, 지켜본 일에 없는 일은 더하지 않는다.",
             ("플레이어가 \"~했다면서요?\"처럼 할 말에 없는 일을 사실로 깔고 물으면, 했다고도 안 했다고도 하지 않는다. "
              "그 일을 이어 말하지 말고 누가 그러더냐고 되묻거나 말을 돌린다.")]
    if job["quiet"]:
        rules.append("화제의 내용은 한 마디도 말하지 않는다.")
    if job["lines"] and not set(job["lines"]) & set(job.get("told", [])):
        rules.append("할 말은 처음 하는 말이다. 아까 말했다고 하지 않는다.")
    user = f"플레이어: {job['said']}" if job["said"] else "플레이어: (말없이 기다린다)"
    if job.get("saw"):   # in the system prompt alone gemma4 let it pass; next to the line it reacts
        user = f"(플레이어가 방금 {job['person']} 앞에서 한 일: {' / '.join(job['saw'])})\n{user}"
    return f"당신은 추리 게임 속 인물 {job['person']}의 목소리다.", rules, user


def make_scene_prompt(job):
    rules = ["플레이어를 \"당신\"이라 부르고 합니다체로 쓴다.",
             "받은 대목과 진실 풀이를 모두 담되 여덟 문장을 넘지 않는다." if job["kind"] == "ending"
             else "두세 문장으로 쓴다.",
             "지어내는 것은 날씨, 소리, 빛 같은 분위기뿐이다. 받은 것에 없는 사람, 물건, 흔적은 그리지 않는다.",
             "분위기는 곳의 모습과 어긋나지 않게 쓴다. '적막', '정적', '어둠' 같은 말을 버릇처럼 넣지 않는다.",
             ("이번에 적힌 것이 많으면 눈에 띄는 두세 가지만 그린다. 그린 것은 적힌 자리와 모양 그대로 쓰고, "
              "여럿을 한 자리에 묶거나 당신이 집어 들었다고 쓰지 않는다.")]
    if job.get("far"):
        rules.append("진행자가 \"그 사이\"로 시작해 다른 곳의 소식을 전하듯 쓴다. 당신은 그 자리에 없으므로 보고 듣는 것처럼 쓰지 않는다.")
    if job["kind"] == "ending":
        rules.append("플레이어의 결론에서 맞힌 것과 틀리거나 비운 것을 바꿔 말하지 않는다. 플레이어를 이름으로 부르지 않는다.")
    if job.get("again"):
        rules.append("이미 와 본 곳이다. 모습은 그리지 않거나 한마디로 줄이되, 모습과 어긋나게 쓰지 않는다.")
    if job.get("people"):
        rules.append("마지막 문장에서 이곳에 있는 사람을 이름으로 알린다.")
    return "당신은 추리 게임의 서술자다.", rules, "장면을 들려준다."


def make_checks(job):
    checks = {"added": noul("쓴 글에 받은 것에 없는 사람, 물건, 때, 곳이 나오는가", "나온다", "나오지 않는다")}
    if job["kind"] == "answer" and job["lines"]:
        checks["meaning"] = noul("쓴 글이 할 말의 뜻을 바꾸지 않고 담고 있는가", "담고 있다", "빠졌거나 바뀌었다")
    if job["kind"] == "answer" and job["quiet"]:
        checks["quiet"] = noul("쓴 글이 사건에 관한 내용을 알려 주지 않는가", "알려 주지 않는다", "알려 준다")
    return checks


def noul(instructions, yes, no):
    return {"type": "noul", "instructions": instructions, "criteria": {"true": yes, "false": no}}


def judge(job, answers, text):
    probs = {key: answers[key]["noul"] for key in make_checks(job)}
    least = {"added": ADDED, "meaning": MEANING, "quiet": QUIET}
    failed = [key for key, p in probs.items() if (1 - p if key == "added" else p) < least[key]]
    if job["kind"] == "answer" and "meaning" not in failed and any(cover(line, text) < COVER for line in job["lines"]):
        failed.append("meaning")
    return failed + list_faults(job, text), probs


def cover(say, text):
    letters = set(re.sub(r"[^가-힣]", "", say))
    return len(letters & set(text)) / len(letters) if letters else 1


def list_faults(job, text):
    kind, unquoted = job["kind"], QUOTED.sub("", text)
    faults = []
    if count_sentences(text) > MAX_SENTENCES[kind] + 2 * max(0, len(job.get("lines", [])) - 1):
        faults.append("length")
    if any(word in text for word in PROMPT_WORDS):
        faults.append("prompt")
    if kind != "answer" and HAEYO.search(unquoted):
        faults.append("style")
    if kind == "dm" and job.get("key") != "conclude" and PUSH.search(unquoted):
        faults.append("push")
    if kind == "dm" and re.search("[\"“”‘’]", text):
        faults.append("speech")
    if any(SequenceMatcher(None, r["answer"], text).ratio() >= REPEAT for r in job.get("recent", [])):
        faults.append("repeat")
    return faults


def count_sentences(text):
    return len([s for s in re.split(r"(?<=[.!?…])\s+", text.strip()) if s])
