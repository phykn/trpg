import re

from .locale import ko
from .rules.state import judge_ending, list_people_here
from .view import find_speaker, show_line, show_name

MEANING = 0.5
ADDED = 0.15
QUIET = 0.5
REWRITES = 2
MAX_SENTENCES = {"answer": 3, "scene": 4, "ending": 8}
MAX_TOKENS = {"answer": 200, "scene": 300, "ending": 700}
LEVELS = {-1: "낮음", 0: "보통", 1: "높음"}


def make_jobs(story, before, after, turn):
    """One job per text slot of the turn's feed, in the same order (view.make_feed)."""
    action, jobs = turn["action"], []
    if action["do"] == "conclude":
        ending = getattr(story.endings, judge_ending(story, after)["verdict"])
        clock, cells = story.head.clock, story.head.cells
        jobs.append({"kind": "ending", "time": ko.clock(clock.start + cells * clock.step) if clock else None,
                     "happening": [ending, story.endings.explain]})
    elif action["do"] not in ("face", "read"):
        speaker = next((find_speaker(story, t) for t in turn["talk"] if find_speaker(story, t)), None)
        jobs.append(make_answer(story, after, turn, speaker) if speaker else make_scene(story, before, after, turn))
    for happened in turn["happened"]:
        event = story.events[happened["omen"] if "omen" in happened else happened["event"]]
        text = event.omen if "omen" in happened else getattr(event, happened["result"])
        jobs.append({"kind": "scene", "happening": [text]})
    return jobs


def make_answer(story, after, turn, person):
    says, quiet = [], True
    repeat = turn["dice"] is not None and turn["action"]["target"] in story.lines
    for item in turn["talk"]:
        kind, value = next(iter(item.items()))
        if kind == "say":
            quiet = False
            says.append(("이 말을 짧게 되풀이한다: " if repeat else "") + story.lines[value].text)
        elif kind == "withhold":
            says.append("이 화제는 말해 주지 않는다")
        elif kind == "pass":
            says.append("답할 것이 없다")
        elif kind == "lead":
            says.append(f'"{value.split(".", 1)[1]}"에 관해서라면 할 말이 있다는 듯 운을 뗀다')
        elif kind == "done":
            says.append("더 말할 것이 없다")
        elif kind == "unsure":
            says.append(f"무엇을 묻는지 되묻는다: {' / '.join(item['topics'])}")
    attitude = after["attitudes"][person]
    return {"kind": "answer", "person": show_name(story, "사람", person), "bio": story.people[person].bio,
            "attitude": f"믿음 {LEVELS[attitude['trust']]}, 두려움 {LEVELS[attitude['fear']]}",
            "said": find_said(story, turn), "says": says, "quiet": quiet and bool(says)}


def find_said(story, turn):
    action = turn["action"]
    if action.get("text"):
        return action["text"]
    if action["do"] == "present":
        return f"(당신이 {ko.eul(show_line(story, action['line']))} 내민다)"
    if action["do"] == "bet":
        return f"(당신이 {ko.METHODS[action['method']]})"
    return None


def make_scene(story, before, after, turn):
    place = after["place"]
    first = turn["action"]["do"] == "stats" or place not in before["visited"]
    written = [show_line(story, c["line"]) for c in turn["changes"]
               if c["op"] == "write" and story.lines[c["line"]].kind == "볼 것"]
    happening = []
    for item in turn["talk"]:
        kind, value = next(iter(item.items()))
        if kind in ("open", "shut"):
            thing = show_line(story, f"볼 것 {story.blocks[value].name}")
            happening.append(f"{thing}이(가) 열린다" if kind == "open" else f"{thing}이(가) 열리지 않는다")
    clock = story.head.clock
    return {"kind": "scene", "intro": story.head.intro if turn["action"]["do"] == "stats" else None,
            "time": ko.clock(clock.start + after["spent"] * clock.step) if clock else None,
            "place": show_name(story, "곳", place), "desc": story.places[place].desc if first else None,
            "written": written, "happening": happening,
            "people": [show_name(story, "사람", p) for p in list_people_here(story, after)]}


def list_given(job):
    if job["kind"] == "answer":
        return [f"신상: {job['bio']}", f"태도: {job['attitude']}", f"할 말: {' / '.join(job['says']) or '없다'}",
                f"플레이어의 말: {job['said'] or '없다'}"]
    given = [f"도입: {job['intro']}"] if job.get("intro") else []
    given += [f"시각: {job['time']}"] if job.get("time") else []
    if job.get("place"):
        given.append(f"곳: {job['place']}" + (f". 모습: {job['desc']}" if job.get("desc") else ""))
    given += [f"이번에 적힌 것: {', '.join(job['written'])}"] if job.get("written") else []
    given += [f"일어난 일: {' '.join(job['happening'])}"] if job.get("happening") else []
    given += [f"이곳의 사람: {', '.join(job['people'])}"] if job.get("people") else []
    return given


def make_messages(job):
    given = "\n".join(g for g in list_given(job) if not g.startswith("플레이어의 말"))
    if job["kind"] == "answer":
        rules = [f"{job['person']}의 대사만 한두 문장으로 쓴다. 이름, 따옴표, 설명은 붙이지 않는다.",
                 "신상의 말투를 따르되 문법에 맞는 한국어로 쓰고, 태도에 맞게 플레이어의 말을 받아친다.",
                 "할 말이 있으면 그 내용을 빠짐없이 말한다. 태도는 말투에만 드러내고, 모른다고 하거나 피하지 않는다.",
                 "할 말의 뜻을 바꾸지 않는다. 할 말에 없는 사람, 물건, 때, 곳을 더하지 않는다.",
                 "할 말이 없으면 신상에 기대어 짧게 받아친다. 사건에 관한 것은 지어내지 않는다."]
        if job["quiet"]:
            rules.append("화제의 내용은 한 마디도 말하지 않는다.")
        head = f"당신은 추리 게임 속 인물 {job['person']}의 목소리다."
    else:
        rules = ["플레이어를 \"당신\"이라 부르고 합니다체로 쓴다.",
                 "받은 대목과 진실 풀이를 모두 담되 여덟 문장을 넘지 않는다." if job["kind"] == "ending"
                 else "두세 문장으로 쓴다.",
                 "지어내는 것은 날씨, 소리, 빛 같은 분위기뿐이다. 받은 것에 없는 사람, 물건, 흔적은 그리지 않는다."]
        if job.get("people"):
            rules.append("마지막 문장에서 이곳에 있는 사람을 이름으로 알린다.")
        head = "당신은 추리 게임의 서술자다."
    system = f"{head}\n\n받은 것:\n{given}\n\n지킬 것:\n" + "\n".join(f"- {r}" for r in rules)
    if job["kind"] == "answer":
        user = f"플레이어: {job['said']}" if job["said"] else "플레이어: (말없이 기다린다)"
    else:
        user = "장면을 들려준다."
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def count_sentences(text):
    return len([s for s in re.split(r"(?<=[.!?…])\s+", text.strip()) if s])


def noul(instructions, yes, no):
    return {"type": "noul", "instructions": instructions, "criteria": {"true": yes, "false": no}}


def make_checks(job):
    checks = {"added": noul("쓴 글에 받은 것에 없는 사람, 물건, 때, 곳이 나오는가", "나온다", "나오지 않는다")}
    if job["kind"] == "answer" and not job["quiet"] and job["says"]:
        checks["meaning"] = noul("쓴 글이 할 말의 뜻을 바꾸지 않고 담고 있는가", "담고 있다", "빠졌거나 바뀌었다")
    if job["kind"] == "answer" and job["quiet"]:
        checks["quiet"] = noul("쓴 글이 사건에 관한 내용을 알려 주지 않는가", "알려 주지 않는다", "알려 준다")
    return checks


def judge(job, answers, text):
    probs = {key: answers[key]["noul"] for key in make_checks(job)}
    failed = [key for key, p in probs.items() if (1 - p if key == "added" else p) < {
        "added": ADDED, "meaning": MEANING, "quiet": QUIET}[key]]
    if count_sentences(text) > MAX_SENTENCES[job["kind"]]:
        failed.append("length")
    return failed, probs


REASONS = {"added": "받은 것에 없는 사람, 물건, 때, 곳을 더했다", "meaning": "할 말의 뜻이 빠졌거나 바뀌었다",
           "quiet": "말하지 않아야 할 내용을 말했다", "length": "너무 길다"}


class Narrator:
    def __init__(self, llm, decision):
        self.llm = llm
        self.decision = decision

    async def check(self, job, text):
        state = "받은 것:\n" + "\n".join(list_given(job)) + f"\n\n쓴 글:\n{text}"
        answers = await self.decision.decide(state, make_checks(job))
        return judge(job, answers, text)

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
