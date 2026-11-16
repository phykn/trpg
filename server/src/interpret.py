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
        kinds = {"topic": f"{show_name(story, '사람', person)}에게 사건이나 다른 사람에 관해 묻는다",
                 "chat": f"인사나 날씨, {show_name(story, '사람', person)} 자신에 관한 잡담이다",
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
        questions["two"] = {"type": "noul", "instructions": "이 문장이 서로 다른 두 가지를 한꺼번에 묻는가",
                            "criteria": {"true": "두 가지를 묻는다", "false": "한 가지만 묻거나 묻지 않는다"}}
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
    if "two" in questions and answers["two"]["noul"] >= TWO_THRESHOLD and probs[ranked[1]] > no_topic:
        return {"kind": "topics", "topics": ranked[:2]}
    rest = max([probs[t] for t in ranked[1:]] + [no_topic])
    if probs[ranked[0]] >= THRESHOLD or probs[ranked[0]] - rest >= MARGIN:
        return {"kind": "topics", "topics": ranked[:1]}
    if kind == "chat":
        return {"kind": "chat"}
    if no_topic >= probs[ranked[0]]:
        return {"kind": "none"}
    return {"kind": "unsure", "topics": ranked[:2]}


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
            heard = pick(answers, questions)
            probs = {key: answers[key]["probabilities"] if q["type"] == "choice" else {"true": answers[key]["noul"]}
                     for key, q in questions.items()}
        except (KeyError, TypeError, AttributeError) as exc:
            raise ModelUnavailable(f"decision: {type(exc).__name__}: {exc}") from None
        return {**heard, "probs": probs}
