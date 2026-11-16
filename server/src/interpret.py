from .locale import ko
from .models import ModelUnavailable
from .names import show_line, show_name
from .rules.act import find_path, list_blocks_here, list_topics
from .rules.state import list_people_here

THRESHOLD = 0.75
TWO_THRESHOLD = 0.85
MARGIN = 0.3   # a topic this far ahead of every other option is taken even under THRESHOLD (engine/01 1절)
NO_TOPIC = "_none"
IMPRESSION_THRESHOLD = 0.5
# A weaker impression still counts when "none" is unlikely; set by the evals of 2026-11-16 (engine/01 1절).
IMPRESSION_LOW, IMPRESSION_NONE_CEILING = 0.35, 0.2
# A threat that also accuses is a threat: 위협 this high outranks a top 의심 (engine/01 1절).
THREAT_OVER_SUSPICION = 0.3
DEED_THRESHOLD = 0.8
SURE_ACTION = 0.5   # an action pick under half the vote, with no told deed, is only guessed (engine/01 1절)
# A reading that passes as nothing yet looks like an action offers that action's dice (engine/01 1절).
GUESS_ACTION = 0.25


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
            answers = settle_kind(answers, questions)
            second = ask_second(answers, questions)
            if second:
                questions = {**questions, "second": second}
                answers = {**answers, **await self.decision.decide(situation, {"second": second})}
            locks = list(list_locks(story, state))
            heard = None if answers["kind"]["choice"] == "action" else pick(answers, questions, locks)
            deed = judge_deed(answers, questions, heard)
            if deed:
                how = ask_how(story, state)
                questions = {**questions, **how}
                answers = {**answers, **await self.decision.decide(situation, how)}
                action = pick_deed("action", answers, questions, locks)
                heard = action if deed == "action" or action["kind"] != "action" else {
                    **heard, "guess": {k: action[k] for k in ("method", "target")}}
            heard = {**heard, "impression": pick_impression(answers, questions)}
            probs = {key: answers[key]["probabilities"] if q["type"] == "choice" else {"true": answers[key]["noul"]}
                     for key, q in questions.items()}
        except (KeyError, TypeError, AttributeError) as exc:
            raise ModelUnavailable(f"decision: {type(exc).__name__}: {exc}") from None
        return {**heard, "probs": probs}

    async def read_impression(self, story, person, text):
        """Only the impression of words that come with a present or a bet."""
        question = ask_impression(story, person)
        situation = f"말하는 상대: {show_name(story, '사람', person)}. 플레이어의 문장: {text}"
        answers = await self.decision.decide(situation, {"impression": question})
        try:
            impression = pick_impression(answers, {"impression": question})
            return {"impression": impression, "probs": {"impression": answers["impression"]["probabilities"]}}
        except (KeyError, TypeError, AttributeError) as exc:
            raise ModelUnavailable(f"decision: {type(exc).__name__}: {exc}") from None


def make_questions(story, state):
    person = state["partner"]
    places = [a[2:] for a in state["notebook"] if a.startswith("곳 ") and find_path(story, state, a[2:])]
    if person:
        name = show_name(story, "사람", person)
        others = [show_name(story, "사람", a[3:]) for a in state["notebook"] if a.startswith("사람 ") and a[3:] != person]
        kinds = {"topic": f"{name}에게 사건이나 {', '.join(others) or '다른 사람'}에 관해 묻는다",
                 "chat": f"인사나 날씨, 부탁, 넋두리, 농담, {name} 자신이나 가족에 관한 잡담처럼 사건과 상관없는 말이다",
                 "look": "누구에게 묻지 않고 주위를 둘러보거나, 이곳이나 수첩의 물건을 들여다보거나 살펴본다"}
    else:
        kinds = {"look": "이곳에 머물며 둘러보거나 혼잣말을 한다"}
    locks = ", ".join(list_locks(story, state).values())
    if person:
        deeds = [f"{ko.eul(name)} 때리거나 멱살을 잡거나 겁주기", "'~하고' 다독이거나 사정하기", "'~라고' 거짓말하거나 넘겨짚어 떠보기"]
        deeds += [f"{ko.eul(locks)} 비틀거나 부수거나 따서 열기"] if locks else []
        kinds["action"] = "묻는 말을 그대로 옮기지 않고 하는 짓을 '~한다'로 적는다. " + ", ".join(deeds)
    elif locks:
        kinds["action"] = f"{ko.eul(locks)} 비틀거나 부수거나 따서 연다"
    questions = {}
    if places:
        kinds["move"] = "다른 곳으로 가려 한다"
        questions["place"] = choice("어디로 가려는가", {p: show_name(story, "곳", p) for p in places})
    questions["kind"] = choice("플레이어가 이 문장으로 무엇을 하려는가", kinds)
    topics = {t: describe_topic(story, person, t) for t in list_topics(story, state, person)} if person else {}
    if topics:
        questions["topic"] = choice("어느 화제를 묻는가", {**topics, NO_TOPIC: "위의 어느 화제도 아니다"})
    things = list_things(story, state)
    if things:
        questions["thing"] = choice("무엇을 들여다보는가", {**things, NO_TOPIC: "어느 것도 아니다. 주위를 둘러보거나 다른 일을 한다"})
    if person:
        questions["impression"] = ask_impression(story, person)
        questions["deed"] = {"type": "noul", "instructions": "이 문장이 상대에게 하는 말이 아니라 플레이어가 하는 짓을 서술하는가",
                             "criteria": {"true": "따옴표 없이 하는 짓을 '~한다'로 서술한다. 예: ~하고 사정한다, ~라고 거짓말한다, "
                                                  "다독인다, 안아 준다, 떠본다",
                                          "false": "상대에게 직접 건네는 말이다. 묻거나 부탁하거나 말을 붙인다"}}
    if len(topics) > 1:
        questions["two"] = {"type": "noul", "instructions": "이 문장이 서로 다른 두 화제를 한꺼번에 묻는가",
                            "criteria": {"true": "서로 다른 두 가지를 묻는다",
                                         "false": "한 가지를 묻거나, 같은 것을 말을 바꿔 거듭 묻는다"}}
    return questions


def list_things(story, state):
    """What can be looked at by name: what the notebook has seen here, and the items in hand (game/07 2절)."""
    return {a: show_line(story, a) for a in state["notebook"] if story.lines[a].kind == "볼 것" and (
        story.lines[a].place == state["place"] or story.things[story.lines[a].name].item)}


def list_locks(story, state):
    return {b.addr: show_name(story, "볼 것", b.name) for b in list_blocks_here(story, state) if b.kind == "잠김"}


def settle_kind(answers, questions):
    """An action picked by under half the vote, with no told deed, is read as the runner-up kind (engine/01 1절)."""
    kind = answers["kind"]
    probs = kind["probabilities"]
    if (kind["choice"] != "action" or "deed" not in questions or probs["action"] >= SURE_ACTION
            or answers["deed"]["noul"] >= DEED_THRESHOLD):
        return answers
    return {**answers, "kind": {**kind, "choice": max((k for k in probs if k != "action"), key=probs.get)}}


def judge_deed(answers, questions, heard):
    """"action" for an action, "guess" for a reading that only looks like one, else None (engine/01 1절).

    A deed told in words ("…하고 사정한다") that would otherwise pass as nothing is an action."""
    if heard is None:
        return "action"
    if "deed" not in questions or heard["kind"] not in ("none", "chat", "unsure"):
        return None
    if answers["deed"]["noul"] >= DEED_THRESHOLD:
        return "action"
    # Kanana says yes to "하는 짓을 서술하는가" for plain questions too (0.6 to 0.74), so it alone guesses nothing
    return "guess" if answers["kind"]["probabilities"].get("action", 0.0) >= GUESS_ACTION else None


def ask_how(story, state):
    """An action is asked apart which method it is, and which lock when there are several (engine/01 1절).

    With no one chosen it is also asked whether it is done to a lock or to someone here: the option of a lock alone
    drew deeds like grabbing a person's arm."""
    locks = list_locks(story, state)
    things = ", ".join(locks.values())
    methods = {**(ko.TRY_METHODS if state["partner"] else {}),
               **({m: f"{ko.eul(things)} {how}" for m, how in ko.OPEN_METHODS.items()} if locks else {})}
    how = {"method": choice("어떤 행동인가", methods)}
    people = {} if state["partner"] else {p: f"{show_name(story, '사람', p)}에게 한다" for p in list_people_here(story, state)}
    if people:
        return {**how, "on": choice("무엇에 하는 짓인가", {**{a: f"{ko.eul(n)} 연다" for a, n in locks.items()}, **people})}
    return {**how, "lock": choice("어느 것을 열려 하는가", locks)} if len(locks) > 1 else how


def ask_impression(story, person):
    own = story.people[person].impressions
    return choice(f"플레이어의 이 말이 {show_name(story, '사람', person)}에게 남기는 인상은 무엇인가",
                  {**ko.IMPRESSIONS, **own, NO_TOPIC: "남기는 인상이 없다. 사건을 묻거나 덤덤하게 말한다"})


def pick_impression(answers, questions):
    if "impression" not in questions:
        return None
    probs = answers["impression"]["probabilities"]
    if answers["impression"]["choice"] not in questions["impression"]["criteria"]:
        raise ModelUnavailable("decision: impression answered outside its options")
    top = max((p for p in probs if p != NO_TOPIC), key=probs.get, default=None)
    if top is None:
        return None
    none = probs.get(NO_TOPIC, 0.0)
    if not (probs[top] >= IMPRESSION_THRESHOLD or probs[top] >= IMPRESSION_LOW and none <= IMPRESSION_NONE_CEILING):
        return None
    return "위협" if top == "의심" and probs.get("위협", 0.0) >= THREAT_OVER_SUSPICION else top


def choice(instructions, criteria):
    return {"type": "choice", "instructions": instructions, "criteria": criteria}


def describe_topic(story, person, topic):
    asks = story.people[person].topics[topic].asks
    return f'"{topic}"에 관해 묻는다' + (f". 예: {' / '.join(asks)}" if asks else "")


def ask_second(answers, questions):
    # One topic's probabilities say nothing about a second, so a sentence that asks two things is asked again which
    # other topic it asks (engine/01 1절).
    if "two" not in questions or answers["kind"]["choice"] in ("move", "look", "action") or (
            answers["two"]["noul"] < TWO_THRESHOLD):
        return None
    probs = answers["topic"]["probabilities"]
    top = max((t for t in probs if t != NO_TOPIC), key=probs.get)
    rest = {t: d for t, d in questions["topic"]["criteria"].items() if t not in (top, NO_TOPIC)}
    return choice(f'이 문장이 "{top}" 말고 또 묻는 화제는 무엇인가',
                  {**rest, NO_TOPIC: "다른 화제는 묻지 않는다. 같은 것을 말을 바꿔 거듭 묻는다"})


def pick_deed(kind, answers, questions, locks):
    if kind == "move":
        return {"kind": "move", "place": answers["place"]["choice"]}
    if kind == "look":
        thing = answers["thing"]["choice"] if "thing" in questions else NO_TOPIC
        return {"kind": "look", **({"thing": thing} if thing != NO_TOPIC else {})}
    on = next((answers[key]["choice"] for key in ("on", "lock") if key in questions), None)
    if "on" in questions and on not in locks:
        return {"kind": "look"}   # done to someone not chosen: writing to no one looks around (game/07 2절)
    method = answers["method"]["choice"]
    return {"kind": "action", "method": method, "target": None if method in ko.TRY_METHODS else on or locks[0]}


def pick(answers, questions, locks=()):
    for key, question in questions.items():
        if question["type"] == "choice" and answers[key]["choice"] not in question["criteria"]:
            raise ModelUnavailable(f"decision: {key} answered outside its options")
    kind = answers["kind"]["choice"]
    if kind in ("move", "look", "action"):
        return pick_deed(kind, answers, questions, locks)
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
