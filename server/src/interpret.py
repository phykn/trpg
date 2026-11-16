from .models import ModelUnavailable
from .rules.act import find_path, list_topics
from .view import show_name

THRESHOLD = 0.75
TWO_THRESHOLD = 0.85
MARGIN = 0.3   # a topic this far ahead of every other option is taken even under THRESHOLD (engine/01 1절)
NO_TOPIC = "_none"


def choice(instructions, criteria):
    return {"type": "choice", "instructions": instructions, "criteria": criteria}


def describe_topic(story, person, topic):
    asks = story.people[person].topics[topic].asks
    return f'"{topic}"에 관해 묻는다' + (f". 예: {' / '.join(asks)}" if asks else "")


def list_places(story, state):
    return [a[2:] for a in state["notebook"] if a.startswith("곳 ") and find_path(story, state, a[2:])]


def make_questions(story, state):
    person = state["partner"]
    places = list_places(story, state)
    if person:
        name = show_name(story, "사람", person)
        others = [show_name(story, "사람", a[3:]) for a in state["notebook"] if a.startswith("사람 ") and a[3:] != person]
        kinds = {"topic": f"{name}에게 사건이나 {', '.join(others) or '다른 사람'}에 관해 묻는다",
                 "chat": f"인사나 날씨, {name} 자신이나 가족에 관한 잡담처럼 사건과 상관없는 말이다",
                 "look": "누구에게 묻지 않고 주위를 둘러보거나 이곳을 살펴본다"}
    else:
        kinds = {"look": "이곳에 머물며 둘러보거나 혼잣말을 한다"}
    questions = {}
    if places:
        kinds["move"] = "다른 곳으로 가려 한다"
        questions["place"] = choice("어디로 가려는가", {p: show_name(story, "곳", p) for p in places})
    questions["kind"] = choice("플레이어가 이 문장으로 무엇을 하려는가", kinds)
    topics = {t: describe_topic(story, person, t) for t in list_topics(story, state, person)} if person else {}
    if topics:
        questions["topic"] = choice("어느 화제를 묻는가", {**topics, NO_TOPIC: "위의 어느 화제도 아니다"})
    if len(topics) > 1:
        questions["two"] = {"type": "noul", "instructions": "이 문장이 서로 다른 두 화제를 한꺼번에 묻는가",
                            "criteria": {"true": "서로 다른 두 가지를 묻는다",
                                         "false": "한 가지를 묻거나, 같은 것을 말을 바꿔 거듭 묻는다"}}
    return questions


def pick(answers, questions):
    for key, question in questions.items():
        if question["type"] == "choice" and answers[key]["choice"] not in question["criteria"]:
            raise ModelUnavailable(f"decision: {key} answered outside its options")
    kind = answers["kind"]["choice"]
    if kind == "move":
        return {"kind": "move", "place": answers["place"]["choice"]}
    if kind == "look":
        return {"kind": "look"}
    if "topic" not in questions:
        return {"kind": "chat" if kind == "chat" else "none"}
    probs = answers["topic"]["probabilities"]
    ranked = sorted((t for t in probs if t != NO_TOPIC), key=probs.get, reverse=True)
    no_topic = probs.get(NO_TOPIC, 0.0)
    if "second" in questions and answers["second"]["choice"] != NO_TOPIC:
        return {"kind": "topics", "topics": [ranked[0], answers["second"]["choice"]]}
    rest = max([probs[t] for t in ranked[1:]] + [no_topic])
    if probs[ranked[0]] >= THRESHOLD or probs[ranked[0]] - rest >= MARGIN:
        return {"kind": "topics", "topics": ranked[:1]}
    if kind == "chat":
        return {"kind": "chat"}
    if no_topic >= probs[ranked[0]]:
        return {"kind": "none"}
    return {"kind": "unsure", "topics": ranked[:2]}


def ask_second(answers, questions):
    """One topic's probabilities say nothing about a second one, so a sentence that asks two things is asked again
    which other topic it asks (engine/01 1절)."""
    if "two" not in questions or answers["kind"]["choice"] in ("move", "look") or (
            answers["two"]["noul"] < TWO_THRESHOLD):
        return None
    probs = answers["topic"]["probabilities"]
    top = max((t for t in probs if t != NO_TOPIC), key=probs.get)
    rest = {t: d for t, d in questions["topic"]["criteria"].items() if t not in (top, NO_TOPIC)}
    return choice(f'이 문장이 "{top}" 말고 또 묻는 화제는 무엇인가',
                  {**rest, NO_TOPIC: "다른 화제는 묻지 않는다. 같은 것을 말을 바꿔 거듭 묻는다"})


class Interpreter:
    def __init__(self, decision):
        self.decision = decision

    async def read(self, story, state, text):
        person = state["partner"]
        questions = make_questions(story, state)
        partner = show_name(story, "사람", person) if person else "없음"
        situation = f"말하는 상대: {partner}. 플레이어의 문장: {text}"
        answers = await self.decision.decide(situation, questions)
        try:
            second = ask_second(answers, questions)
            if second:
                questions = {**questions, "second": second}
                answers = {**answers, **await self.decision.decide(situation, {"second": second})}
            heard = pick(answers, questions)
            probs = {key: answers[key]["probabilities"] if q["type"] == "choice" else {"true": answers[key]["noul"]}
                     for key, q in questions.items()}
        except (KeyError, TypeError, AttributeError) as exc:
            raise ModelUnavailable(f"decision: {type(exc).__name__}: {exc}") from None
        return {**heard, "probs": probs}
