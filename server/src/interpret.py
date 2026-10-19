"""Free text to steps: one Kev call of closed questions about the player's sentence, then pure assembly.

Kev reads only the sentence; the scene reaches it through the option descriptions. Measured on the
harbor eval set, putting the scene text into Kev's state cut first-step accuracy from 26/58 to 9/58.
"""

import re
from typing import Any

from pydantic import Field

from src.content.schema import APPROACHES, PLAYER, Model, Story
from src.locale import ko
from src.models.kev import Answer, KevClient, ModelUnavailable
from src.rules.candidates import Candidate, candidates
from src.rules.resolve import best_fit, default_approach
from src.scene.build import Scene, build
from src.world import query
from src.world.state import ActionStep, GameState, ImproviseStep, Step, TalkStep, Uses

MAX_STEPS = 3
NONE = "none"
IMPROVISE = "improvise"
CLARIFY_FLOOR = 0.1
# Tuned for Kev 4B on scenarios/harbor/evals (see code.md 8.2). Kev spreads probability over many options,
# so absolute confidence is low even when its first choice is right; these compare options instead.
SAME_VERB_MARGIN = 1.6   # ask back when the top two share a verb and the first is not this much ahead
NEXT_STEP_FLOOR = 0.2    # a later step must reach this probability and differ from the step before
REJECT_CONFIDENCE = 0.8
LABEL_OVERLAP = 0.6      # a sentence this close to an open solution's label is that solution
ACT_OVERLAP = 0.4
ACT_LABEL_OVERLAP = 0.45  # authored action labels are long sentences; this much of one is that action        # a later authored action must be this present in the words
CLOSE_MARGIN = 1.2       # two concrete readings this close are asked back
CLOSE_FLOOR = 0.2
LINK_OVERLAP = 0.3       # a sentence this close to an obstacle's words is about it
COMMON = {"당신", "그는", "하는", "있습", "있습니", "합니", "니다", "다른", "이름", "받을", "있는", "하면", "확인하"}
SECOND_OPINION_BELOW = 0.5  # Qwen picks the first step when Kev's best is below this
PRESS_FLOOR = 0.4        # talk counts as an attempt on an obstacle at this probability
PRESS_CUE_FLOOR = 0.2    # or at this one when the sentence also names an approach  # reject as impossible only when Kev is this sure


class Rejected(Model):
    reason: str


class Clarify(Model):
    options: list[tuple[str, str]]


class Steps(Model):
    steps: list[Step] = Field(min_length=1)


Interpretation = Rejected | Clarify | Steps


def _choice(text: str, criteria: dict[str, str]) -> dict[str, Any]:
    return {"type": "choice", "instructions": text, "criteria": criteria}


def _noul(text: str, yes: str, no: str) -> dict[str, Any]:
    return {"type": "noul", "instructions": text, "criteria": {"true": yes, "false": no}}


def step_questions(cands: dict[str, Candidate]) -> dict[str, dict]:
    """First call: only which actions the sentence holds."""
    offered = {c.id: c.label for c in cands.values() if c.kev and c.enabled and c.kind != "improvise"}
    q: dict[str, dict] = {"s1": _choice(ko.FIRST_STEP_QUESTION, {**offered, IMPROVISE: ko.IMPROVISE})}
    for i in range(2, MAX_STEPS + 1):
        q[f"s{i}"] = _choice(ko.NEXT_STEP_QUESTION.format(n=i), {**offered, IMPROVISE: ko.IMPROVISE, NONE: ko.NONE_STEP})
    return q


def detail_questions(story: Story, scene: Scene, chosen: list[str]) -> dict[str, dict]:
    """Second call: details only for the improvise and talk steps that were chosen."""
    q: dict[str, dict] = {}
    targets = {o.id: f"{o.name} {o.value}/{o.boxes}" for o in scene.obstacles}
    targets |= {t.id: t.name for t in scene.tags if t.kind == "snag"}
    edges = {t.id: t.name for t in scene.tags if t.kind == "edge"}
    things = {x.id: x.name for x in [*scene.carried, *scene.knowledge, *scene.skills]}
    traits = {t.id: f"{t.name}: {t.text}" for t in scene.traits}
    approaches = {a: f"{scene.approach_names[a]}: {ko.APPROACH_HINT[a]}" for a in APPROACHES}
    for i, choice in enumerate(chosen, 1):
        if choice != IMPROVISE:
            continue
        detail = {
            "target": _choice(ko.TARGET_QUESTION.format(n=i), targets),
            "approach": _choice(ko.APPROACH_QUESTION.format(n=i), approaches),
            "plausible": _choice(ko.PLAUSIBLE_QUESTION.format(n=i), dict(ko.PLAUSIBLE)),
            "uses.tag": _choice(ko.USES_TAG_QUESTION.format(n=i), {**edges, NONE: ko.NONE_OPTION}),
            "uses.thing": _choice(ko.USES_THING_QUESTION.format(n=i), {**things, NONE: ko.NONE_OPTION}),
            "uses.trait": _choice(ko.USES_TRAIT_QUESTION.format(n=i), {**traits, NONE: ko.NONE_OPTION}),
        }
        for key, question in detail.items():
            if question["type"] == "noul" or len(question["criteria"]) > 1:
                q[f"s{i}.{key}"] = question
    talk = next((c.partition(":")[2] for c in chosen if c.startswith("talk:")), None)
    person = next((p for p in scene.people if p.id == talk), None)
    if person is not None:
        c = story.characters[person.id]
        topics = {t.id: t.name for t in person.topics}
        lies = {k: f"{story.knowledge[k].title}: {story.knowledge[k].summary}" for k in c.knows}
        q["talk.topic"] = _choice(ko.TOPIC_QUESTION.format(name=person.name), {**topics, "chat": ko.CHAT})
        # Words aimed at an obstacle ("this ink is different") are not chat: without this they were a turn
        # that changed nothing. Asked in the same call, so it costs no extra round trip.
        if scene.obstacles:
            q["talk.press"] = _choice(ko.PRESS_QUESTION.format(name=person.name),
                                      {**{o.id: o.name for o in scene.obstacles}, NONE: ko.PRESS_NONE})
            q["talk.approach"] = _choice(ko.APPROACH_QUESTION.format(n=1),
                                         {a: f"{scene.approach_names[a]}: {ko.APPROACH_HINT[a]}" for a in APPROACHES})
        q["talk.attitude"] = _choice(ko.ATTITUDE_QUESTION.format(name=person.name), dict(ko.ATTITUDES))
        q["talk.claim"] = _noul(ko.CLAIM_QUESTION, ko.CLAIM_YES, ko.CLAIM_NO)
        q["talk.touch"] = _choice(
            ko.TOUCH_QUESTION.format(name=person.name),
            {"desire": f"{ko.TOUCH['desire']} ({c.desire})", "fear": f"{ko.TOUCH['fear']} ({c.fear})",
             "none": ko.TOUCH["none"]},
        )
        # One stance question per fact: asked to pick "the fact the words contradict", Kev picks the related
        # fact even when the player agrees with it, which turned true claims into exposed lies.
        for k, fact in lies.items():
            q[f"talk.lie.{k}"] = _choice(ko.fill(ko.STANCE_QUESTION, fact=fact), dict(ko.STANCES))
    return q


def _pick(answers: dict[str, Answer], key: str, default=None):
    """Detail answers are taken at their best guess; a missing question means its only option."""
    answer = answers.get(key)
    if answer is None or answer.answer == NONE:
        return default
    return answer.answer


def _sure(answers: dict[str, Answer], key: str) -> bool:
    answer = answers.get(key)
    return answer is not None and answer.answer is True and not answer.low


def _uses(answers: dict[str, Answer], i: int, named_trait: str | None = None) -> Uses:
    return Uses(tag=_pick(answers, f"s{i}.uses.tag"), thing=_pick(answers, f"s{i}.uses.thing"),
                trait=named_trait or _pick(answers, f"s{i}.uses.trait"))


def trait_named(story: Story, state: GameState, text: str) -> str | None:
    """A trait of the player's that the sentence calls on by a word of its name ("갑판원 시절 솜씨로")."""
    hits = [t for t in state.player.traits
            if any(w in text for w in story.trait(t).name.split() if len(w) >= 2)]
    return hits[0] if len(hits) == 1 else None


def _clarify(answer: Answer, cands: dict[str, Candidate]) -> Clarify | None:
    """Ask back only when the two best options are the same kind of action and close."""
    ranked = sorted(answer.probabilities.items(), key=lambda kv: -kv[1])
    if len(ranked) < 2:
        return None
    (top, p1), (second, p2) = ranked[0], ranked[1]
    verb = top.partition(":")[0]
    if verb == IMPROVISE or second.partition(":")[0] != verb or p1 >= SAME_VERB_MARGIN * p2:
        return None
    options = [k for k, p in ranked if k.startswith(f"{verb}:") and p >= CLARIFY_FLOOR and k in cands][:3]
    return Clarify(options=[(k, cands[k].label) for k in options]) if len(options) >= 2 else None


def approach_cue(text: str) -> str | None:
    """The one approach whose verb cues the sentence uses, if exactly one does. A sentence that ends in
    a look ("한 줄씩 짚어 가며 읽는다") is a look, whatever verbs lead up to it."""
    last = text.strip().split()[-1] if text.strip() else ""
    if any(c in last for c in ko.LOOK_CUES + ["읽"]):
        return None
    for peek in ko.PEEKS:
        text = text.replace(peek, " ")
    hits = [a for a, cues in ko.APPROACH_CUES.items() if any(c in text for c in cues)]
    return hits[0] if len(hits) == 1 else None


def purpose_for(story: Story, target: str | None, text: str) -> str:
    if target in story.obstacles:
        return "setup" if any(c in text for c in ko.SETUP_CUES) else "overcome"
    return "clear" if target else "overcome"


def linked(story: Story, state: GameState, scene: Scene, obstacle: str, text: str, by_person: bool = True) -> bool:
    """Whether the sentence touches the obstacle at all: its name, its solutions, the clues and items they
    need, or the person in its name (by name or role word). Kev's target question always names some
    obstacle, so "sit on a crate and rest" rolled against the cargo door."""
    o = story.obstacles[obstacle]
    own = [o.name, *(sol.label for sol in o.solutions)]
    if any(overlap(w, text) >= LINK_OVERLAP for w in own):
        return True
    if any(st in text for st in _stems(story, own)):
        return True  # a word only this obstacle's words use ("등불" for the dark lamp)
    if overlap_any(story, state, obstacle, text):
        return True
    if not by_person:
        return False
    for p in scene.people:
        if p.name in o.name and (p.name in text or any(w in text for w in p.role.split() if len(w) >= 2)):
            return True
    return False


def _stems(story: Story, texts: list[str]) -> set[str]:
    """Noun-like stems of the texts, without people's and places' names, role words and verbs."""
    names = {n for table in (story.characters, story.places) for x in table.values() for n in x.name.split()}
    names |= {w for c in story.characters.values() for w in c.role.split()}
    stems = {t[:-1] if len(t) >= 3 else t for x in texts for t in re.findall(r"[가-힣]{2,}", x) if not t.endswith("다")}
    return {st for st in stems - names - COMMON if len(st) >= 2 and st not in {n[:-1] for n in names}}


def overlap_any(story: Story, state: GameState, obstacle: str, text: str) -> bool:
    """The words reach the obstacle through what its solutions need: a word of the clue ("잉크" in the
    forged list) or the item's name. Names of people and places say nothing about which obstacle."""
    o = story.obstacles[obstacle]
    texts = []
    for sol in o.solutions:
        for c in sol.requires:
            # Only a clue or item the player has: words about what they have not found link to nothing.
            if c.kind == "knows" and c.target in story.knowledge and query.knows(state.graph, PLAYER, c.target):
                texts += [story.knowledge[c.target].title, story.knowledge[c.target].summary]
            elif c.kind == "carries" and c.target in query.carried(state.graph):
                texts.append(story.name(c.target))
    return any(st in text for st in _stems(story, texts))


def addressee(text: str, scene: Scene) -> str | None:
    """The present person the sentence speaks to: named (or called by a word of their role, with a suffix
    such as '주인장') with a to-person particle and a speech verb; or the only person here when a strong
    speech verb has no one else to go to."""
    called = re.match(r"^\s*[가-힣]{1,6}(?:\s?[가-힣]{1,3})?\s*,", text) is not None
    if not called and not any(c in text for c in ko.TALK_CUES + ko.SPEAK_CUES):
        return None
    hits = []
    for p in scene.people:
        words = [re.escape(w) for w in [p.name, *[w for w in p.role.split() if len(w) >= 2]]]
        to = rf"(?:{'|'.join(words)})\S?(?:에게|한테|께)"
        obj = rf"(?:{'|'.join(words)})\S?(?:을|를)\s?.{{0,14}}(?:{'|'.join(ko.PERSUADE_OBJECT)})"
        call = rf"^\s*(?:{'|'.join(words)})\s?(?:{'|'.join(ko.VOCATIVE)})?\s*,"
        if re.search(to, text) or re.search(obj, text) or re.search(call, text):
            hits.append(p.id)
    if len(hits) == 1:
        return hits[0]
    others = [p.id for p in scene.people if not p.companion]
    if not hits and len(others) == 1 and any(c in text for c in ko.SPEAK_CUES):
        return others[0]
    return None


def named_gift(story: Story, scene: Scene, cands: dict[str, Candidate], text: str) -> str | None:
    """'<person>에게 <held item>을 주고/건네': the one gift the words spell out."""
    hits = [cid for cid, c in cands.items() if c.kind == "give"
            and f"{story.name(cid.split(':')[1])}에게" in text
            and any(w in text for w in story.name(cid.split(':')[2]).split() if len(w) >= 2)]
    return hits[0] if len(hits) == 1 else None


def attitude_cue(text: str) -> str | None:
    hits = [a for a, cues in ko.ATTITUDE_CUES.items() if any(c in text for c in cues)]
    return hits[0] if len(hits) == 1 else None


def claims(text: str) -> bool:
    return re.search(ko.CLAIM_PATTERN, text) is not None


def look_or_take(text: str, chosen: list[str], answer: Answer | None) -> list[str]:
    """Kev splits "살펴본다" between taking and looking at the same thing; the verb decides."""
    if not chosen or answer is None:
        return chosen
    kind, _, target = chosen[0].partition(":")
    other = {"take": "inspect", "inspect": "take"}.get(kind)
    if other is None or f"{other}:{target}" not in answer.probabilities:
        return chosen
    look = any(c in text for c in ko.LOOK_CUES)
    take = any(c in text for c in ko.TAKE_CUES)
    if look != take:
        chosen = [f"{'inspect' if look else 'take'}:{target}", *chosen[1:]]
    return chosen


def _pressed(answers: dict[str, Answer], cue: str | None) -> str | None:
    """The obstacle the words to a person aim at. Kev 0.8B splits this question close to even (0.50 for
    pleading, 0.19 for small talk), so the bar is a probability, lowered when a verb names an approach."""
    press = answers.get("talk.press")
    if press is None:
        return None
    best = max((k for k in press.probabilities if k != NONE), key=press.probabilities.get, default=None)
    if best is None:
        return None
    p = press.probabilities[best]
    if cue and len(press.probabilities) == 2:
        # One obstacle here and words that name an approach ("persuade him to open the door"): that is it.
        return best
    return best if p >= PRESS_FLOOR or (cue and p >= PRESS_CUE_FLOOR) else None


def stem(name: str) -> str:
    """A name without its last syllable when long enough: '정정 명령서' also matches '정정 명령을'."""
    return name[:-1] if len(name.replace(" ", "")) >= 4 else name


def bigrams(text: str) -> set[str]:
    squeezed = "".join(text.split())
    return {squeezed[i : i + 2] for i in range(len(squeezed) - 1)}


def mentions(name: str, text: str) -> bool:
    """A word of the name standing on its own in the sentence ("압송선" is not "압송 명단"); a one-syllable
    word only with a particle ("문을")."""
    tail = r"(?:을|를|이|가|에|의|은|는|으로|로|과|와|도|만|에게)?(?![가-힣])" 
    return any(re.search(re.escape(w) + (tail if len(w) >= 2 else r"(?:을|를|이|가|에|의|은|는|으로|로)"), text)
               for w in name.split())


def overlap(label: str, text: str) -> float:
    """Share of the label's letter pairs found in the sentence: '등불 앞을 두 번 가린다' covers 6/7 of '등불을 두 번 가린다'."""
    pairs = bigrams(label)
    return len(pairs & bigrams(text)) / len(pairs) if pairs else 0.0


def named_solution(story: Story, cands: dict[str, Candidate], text: str) -> str | None:
    """An open authored solution (or authored action) whose required item or clue the sentence names, or
    whose label it nearly repeats. Using what the solution needs is that solution: "show the guard the order" must not be a lucky
    roll or a gift, and the buttons are button-only for Kev, so the words have to find them here."""
    hits = []
    for cid, cand in cands.items():
        if cand.kind == "act" and cand.enabled and overlap(cand.label, text) >= ACT_LABEL_OVERLAP:
            hits.append(cid)
            continue
        if cand.kind != "solve" or not cand.enabled:
            continue
        _, oid, n = cid.split(":")
        needs = [c.target for c in story.obstacles[oid].solutions[int(n)].requires if c.kind in ("carries", "knows")]
        if any(stem(story.name(t)) in text for t in needs) or overlap(cand.label, text) >= LABEL_OVERLAP:
            hits.append(cid)
    return hits[0] if len(hits) == 1 else None


def route(state: GameState, story: Story, text: str) -> list[str] | None:
    """Moves along open exits to the one known place the sentence names with a movement verb."""
    if not any(c in text for c in ko.MOVE_CUES):
        return None
    start = query.place_of(state.graph, PLAYER)
    last = {}
    for pid, p in story.places.items():
        w = p.name.split()[-1]
        last[w] = None if w in last else pid  # a word two places share names neither
    named = [pid for pid, p in story.places.items() if pid != start and p.name in text]
    if not named:
        named = [pid for w, pid in last.items() if pid and pid != start and len(w) >= 2 and w in text]
    if len(named) != 1:
        return None
    paths, frontier = {start: []}, [start]
    while frontier:
        nxt = []
        for here_ in frontier:
            for dst, is_open in query.exits(state.graph, here_):
                if is_open and dst not in paths:
                    paths[dst] = [*paths[here_], f"move:{dst}"]
                    nxt.append(dst)
        frontier = nxt
    path = paths.get(named[0])
    return path if path and len(path) <= MAX_STEPS else None


def _before_route(story: Story, state: GameState, scene: Scene, cands: dict[str, Candidate], text: str) -> str | None:
    """The step a clause ending in '-고' says before the walk: a look at a named thing, or an attempt on an
    obstacle here that the clause touches."""
    place = next((p.name for p in story.places.values() if p.name in text), None) or next(
        (p.name.split()[-1] for p in story.places.values() if len(p.name.split()[-1]) >= 2 and p.name.split()[-1] in text), None)
    cut = text.find(place) if place else -1
    if cut <= 0:
        cut = min((text.find(w) for w in ko.MOVE_CUES if w in text), default=-1)
    head = text[:cut] if cut > 0 else ""
    if not re.search(r"(?:고|다음|뒤에|후에)\s", head + " "):
        return None
    if any(c in head for c in ko.LOOK_CUES):
        looks = [c for c in cands if c.startswith("inspect:")]
        best = max(looks, key=lambda c: overlap(cands[c].label, head), default=None)
        if best and overlap(cands[best].label, head) >= 0.3:
            return best
    tied = [o.id for o in scene.obstacles if linked(story, state, scene, o.id, head, by_person=False)]
    return tied[0] if len(tied) == 1 else None


def _role_words(story: Story, character: str) -> list[str]:
    """Role words that name the person, not a place they share a word with ("선술집 주인" is not "선술집")."""
    places = {w for p in story.places.values() for w in p.name.split()}
    return [w for w in story.characters[character].role.split() if len(w) >= 2 and w not in places]


def _look_score(story: Story, cands: dict[str, Candidate], cid: str, text: str) -> float:
    target = cid.partition(":")[2]
    if target in story.obstacles and any(st in text for st in _stems(story, [story.obstacles[target].name,
                                                                         *(x.label for x in story.obstacles[target].solutions)])):
        return 1.0  # a word only this obstacle uses ("그을린 등불") names it
    described = story.items[target].text if target in story.items else ""
    # A long description dilutes its own share; measure how much of the sentence it covers instead.
    return max(overlap(cands[cid].label, text), overlap(text, described) if described else 0.0)


def _close_call(answer: Answer | None, cands: dict[str, Candidate], text: str) -> Clarify | None:
    """Ask back when Kev's two best concrete readings are nearly tied and no plain word settled it;
    a wrong guess costs a roll or a step, a question costs a tap."""
    if answer is None:
        return None
    ranked = [(k, p) for k, p in sorted(answer.probabilities.items(), key=lambda kv: -kv[1]) if k in cands]
    if len(ranked) < 2 or IMPROVISE in (ranked[0][0], ranked[1][0]):
        return None
    (top, p1), (second, p2) = ranked[0], ranked[1]
    if p2 < CLOSE_FLOOR or p1 >= CLOSE_MARGIN * p2:
        return None
    if abs(overlap(cands[top].label, text) - overlap(cands[second].label, text)) >= 0.2:
        return None  # the words name one of them: "화물문 걸쇠" is the latch, not the clerk's watch
    if {top.partition(":")[0], second.partition(":")[0]} == {"inspect", "take"} and (
            any(c in text for c in ko.LOOK_CUES) != any(c in text for c in ko.TAKE_CUES)):
        return None  # the verb already told a look from a grab
    return Clarify(options=[(top, cands[top].label), (second, cands[second].label)])


def _target(answers: dict[str, Answer], scene: Scene, i: int) -> str | None:
    options = [o.id for o in scene.obstacles] + [t.id for t in scene.tags if t.kind == "snag"]
    if len(options) == 1:
        return options[0]
    return _pick(answers, f"s{i}.target")


def chosen_steps(answers: dict[str, Answer], cands: dict[str, Candidate]) -> list[str] | Clarify:
    clarify = _clarify(answers["s1"], cands)
    if clarify is not None:
        return clarify
    chosen: list[str] = []
    for i in range(1, MAX_STEPS + 1):
        answer = answers.get(f"s{i}")
        if answer is None:
            break
        choice = str(answer.answer)
        # Kev tends to repeat the first action when asked for the next one; a repeat means no next step.
        if i > 1 and (choice in (NONE, chosen[-1]) or answer.probabilities.get(choice, 0.0) < NEXT_STEP_FLOOR):
            break
        chosen.append(choice)
    return chosen


def assemble(
    story: Story, state: GameState, cands: dict[str, Candidate], answers: dict[str, Answer], text: str = ""
) -> Interpretation:
    chosen = chosen_steps(answers, cands)
    asked = chosen if isinstance(chosen, Clarify) else None
    if asked is not None:
        # Kev was torn, but plain words may still settle it ("모라가 써 준 쪽지를 내민다" names the solution).
        chosen = [str(answers["s1"].answer)]
    scene = build(story, state)
    kev_first = chosen[0] if chosen else None
    chosen = look_or_take(text, chosen, answers.get("s1"))
    person = addressee(text, scene)
    if person is not None and f"talk:{person}" in cands and f"talk:{person}" not in chosen:
        chosen = [f"talk:{person}", *[c for c in chosen if not c.startswith("talk:") and c != IMPROVISE]][:MAX_STEPS]
    if person is not None:
        # Kev reads "show the guard the order and tell him to free Naru" as a gift to Naru, and "ask the way
        # into the prison" as going there: words to a person give only to that person and walk nowhere.
        chosen = [c for c in chosen if not (c.startswith("give:") and c.split(":")[1] != person)
                  and not c.startswith("move:")]
    path = route(state, story, text)
    forced: dict[int, str] = {}
    if path is not None and not person:
        # "Go to the tower with Naru" from two rooms away became a look at Naru: walk the open path.
        # A clause before it ("명단을 확인하고 …", "유리를 닦아 불을 붙이고 …") is its own first step.
        first = _before_route(story, state, scene, cands, text)
        if first is None:
            chosen = path
        elif first.startswith("inspect:"):
            chosen = [first, *path][:MAX_STEPS]
        else:
            chosen, forced[1] = [IMPROVISE, *path][:MAX_STEPS], first
    prize = next((i for o in scene.obstacles for i in story.obstacles[o.id].guards
                  if f"inspect:{i}" in cands and mentions(story.name(i), text)), None)
    if prize is not None and chosen and any(c in text for c in ko.TAKE_CUES) and not chosen[0].startswith(("inspect:", "take:")):
        chosen = [f"inspect:{prize}", *chosen[1:]]  # the guard rule below makes it an attempt on its guard
    last = " ".join(text.split()[-2:])
    grab = next((c for c in cands if c.startswith("take:") and mentions(story.name(c[5:]), text)), None)
    if grab and any(t in last for t in ko.TAKE_CUES) and chosen and not chosen[0].startswith(("give:", "move:")):
        chosen = [grab, *[c for c in chosen[1:] if c != grab]]  # the final verb takes the thing the words name
    looking = any(c in text for c in ko.LOOK_CUES + ko.SENSE_CUES)
    if chosen and looking and (chosen[0] == IMPROVISE or chosen[0].startswith("inspect:")):
        # "이든을 유심히 관찰한다" is a look at Eden, not at Eden's watch; "게시판에 붙은 종이를 들여다본다"
        # looks at the notice its description names: the best-named thing to look at.
        looks = {c: _look_score(story, cands, c, text) for c in cands if c.startswith("inspect:")}
        best = max(looks, key=looks.get, default=None)
        here = looks.get(chosen[0], 0.0)
        if best and looks[best] >= LINK_OVERLAP and looks[best] > here:
            chosen = [best, *chosen[1:]]
    # Steps that cannot be taken back need the words for them: a gift a giving verb, a later authored
    # action its own label. Kev's later steps are guesses (NEXT_STEP_FLOOR is 0.2).
    shown = re.sub(r"보여\s?주", "", text)  # showing is not giving
    gives = any(c in shown for c in ko.GIVE_CUES)
    # Later look and take steps need their own verb: Kev added "take the notice" to "show her the list".
    chosen = [c for i, c in enumerate(chosen) if i == 0 or not (
        (c.startswith("take:") and not any(t in text for t in ko.TAKE_CUES))
        or (c.startswith("inspect:") and not any(t in text for t in ko.LOOK_CUES + ko.SENSE_CUES)))]
    chosen = [c for i, c in enumerate(chosen) if not (c.startswith("give:") and not (
                  gives and any(w in text for w in story.name(c.split(":")[2]).split() if len(w) >= 2)))
              and not (i > 0 and c.startswith("act:") and c in cands and overlap(cands[c].label, text) < ACT_OVERLAP)]
    gift = named_gift(story, scene, cands, text) if gives else None
    ends_giving = gift is not None and any(c in (text.strip().split() or [""])[-1] for c in ko.GIVE_CUES)
    if gift is not None and (gift not in chosen or ends_giving):
        # The final verb is the deed: "도윤 몰래 … 나루에게 붕대를 건넨다" is a gift done quietly, not an attempt.
        # "Give Mora the bandage and go to the prison": Kev kept the walk and lost the gift.
        chosen = [gift, *[c for c in chosen if not c.startswith(("give:", "talk:")) and c != IMPROVISE]][:MAX_STEPS]
    solve = named_solution(story, cands, text)
    if solve is not None:
        chosen = [solve, *[c for c in chosen if not c.startswith(("talk:", "give:", "solve:", "act:")) and c != IMPROVISE]][:MAX_STEPS]
    settled = person is not None or path is not None or solve is not None or gift is not None or chosen[:1] != [kev_first]
    if asked is not None and not settled:
        ranked = sorted(asked.options, key=lambda o: -overlap(o[1], text))
        if overlap(ranked[0][1], text) - overlap(ranked[1][1], text) < 0.2:
            return asked
        chosen = [ranked[0][0]]  # the words name one of them
    if chosen and not settled:
        close = _close_call(answers.get("s1"), cands, text)
        if close is not None:
            return close
    steps: list[Step] = []
    talked = False
    cue = approach_cue(text)
    trait = trait_named(story, state, text)
    for i, choice in enumerate(chosen, 1):
        target_of = choice.partition(":")[2]
        guard = next((oid for oid, o in story.obstacles.items() if target_of in o.guards
                      and state.obstacles[oid].value < o.boxes and o.place == scene.place.id), None)
        if choice.startswith(("inspect:", "take:")) and guard and (cue or any(c in text for c in ko.TAKE_CUES)):
            # Taking what an obstacle still guards ("slip the ledger away while the clerk turns") is an
            # attempt on that obstacle, not a look at the ledger.
            steps.append(ImproviseStep(purpose="overcome", target=guard, approach=cue or best_fit(story, state, guard),
                                       risk="normal", plausibility="natural", check=True))
            continue
        person_obstacle = next((o.id for o in scene.obstacles if target_of in story.characters
                                and story.characters[target_of].name in o.name), None)
        if choice.startswith("inspect:") and cue and person_obstacle:
            # "짚어 보인다" to the inspector is a move on her doubt, not a look at her.
            steps.append(ImproviseStep(purpose=purpose_for(story, person_obstacle, text), target=person_obstacle,
                                       approach=cue, risk="normal", plausibility="natural", check=True))
            continue
        if choice.startswith("inspect:") and not cue and any(c in text for c in ko.LOOK_CUES + ko.SENSE_CUES) \
                and not mentions(story.name(target_of), text) and not (
                    target_of in story.characters and any(w in text for w in _role_words(story, target_of))) \
                and _look_score(story, cands, choice, text) < LINK_OVERLAP:
            # A look at nothing the words name ("창고 구석의 그림자를 둘러본다") is just looking around.
            steps.append(ImproviseStep(purpose="overcome", target=None, approach=default_approach(state),
                                       risk="normal", plausibility="natural", check=False))
            continue
        if choice.startswith("inspect:") and target_of in story.obstacles and (cue or not any(c in text for c in ko.LOOK_CUES)):
            # "Steal the keys while he dozes" or "wipe the soot off the lamp" is not a look at the obstacle:
            # without a looking verb, Kev's look is an attempt.
            steps.append(ImproviseStep(purpose=purpose_for(story, target_of, text), target=target_of,
                                       approach=cue or best_fit(story, state, target_of),
                                       risk="normal", plausibility="natural", check=True))
            continue
        if choice == IMPROVISE:
            plausible = answers.get(f"s{i}.plausible")
            if plausible is not None and plausible.answer == "impossible" and plausible.confidence >= REJECT_CONFIDENCE:
                if i == 1:
                    return Rejected(reason=ko.WHY_NOT["beyond"])
                break
            # Rules decide what Kev answered unreliably: purpose follows the target, a sentence with
            # nothing to act on is a no-roll moment, and risk starts normal (check.risk_of raises it).
            target = forced.get(i) or _target(answers, scene, i)
            named = target and overlap(story.name(target), text) >= 0.5
            if i not in forced and not cue and not named and any(c in text for c in ko.SENSE_CUES):
                target = None
            if i not in forced and text and target in story.obstacles and not cue and not linked(story, state, scene, target, text):
                target = None  # nothing in the words points at the obstacle: a moment, not a roll
            steps.append(ImproviseStep(
                purpose=purpose_for(story, target, text),
                target=target,
                approach=cue or (best_fit(story, state, target) if i in forced else
                                 _pick(answers, f"s{i}.approach", default_approach(state))),
                risk="normal",
                # A stretch makes the step high risk, so an unsure answer must not raise it.
                plausibility="stretch" if plausible is not None and plausible.answer != "natural" and not plausible.low
                else "natural",
                check=target is not None,
                uses=_uses(answers, i, trait),
            ))
        elif choice.startswith("talk:") and not talked:
            talked = True
            character = choice.partition(":")[2]
            topic = _pick(answers, "talk.topic", "chat")
            if not any(t.id == topic and t.character == character for t in story.topics):
                topic = "chat"
            if topic == "chat":
                # "Ask what kind of man the guard Doyun is" names the topic 'guard Doyun'; Kev called it chat.
                speaks = any(c in text for c in ko.TALK_CUES + ko.SPEAK_CUES)
                named = [t.id for t in story.topics if t.character == character
                         and (overlap(t.title, text) >= LABEL_OVERLAP
                              or (speaks and any(w in text for w in t.title.split() if len(w) >= 2)))]
                topic = named[0] if len(named) == 1 else topic
            lie = next((k[len("talk.lie."):] for k, a in answers.items()
                        if k.startswith("talk.lie.") and a.answer == "deny" and not a.low), None)
            tied = [o.id for o in scene.obstacles if linked(story, state, scene, o.id, text, by_person=False)]
            asks = any(q in text for q in ko.QUESTION_CUES)
            aim = None if asks and not cue else (
                _pressed(answers, cue) or (tied[0] if len(tied) == 1 and (cue or overlap_any(story, state, tied[0], text)) else None))
            speaks = any(c in text for c in ko.TALK_CUES + ko.SPEAK_CUES)
            near = [o.id for o in scene.obstacles if linked(story, state, scene, o.id, text)]
            offers = any(c in text for c in ko.OFFER_CUES)
            if (not speaks and cue or offers) and len(near) == 1:
                # "Stand by the clerk and help count" names no speech: it is an attempt, whatever topic Kev saw.
                topic, aim = "chat", near[0]
            if topic == "chat" and not lie and not _sure(answers, "talk.claim") and not claims(text) \
                    and attitude_cue(text) not in ("deceive", "threaten") and aim:
                steps.append(ImproviseStep(
                    purpose="overcome", target=aim, risk="normal", plausibility="natural", check=True,
                    approach=cue or _pick(answers, "talk.approach", "charm"), uses=_uses(answers, i, trait),
                ))
                continue
            steps.append(TalkStep(
                character=character,
                topic=topic,
                attitude=attitude_cue(text) or _pick(answers, "talk.attitude", "polite"),
                claim=_sure(answers, "talk.claim") or claims(text),
                touch=_pick(answers, "talk.touch", "none"),
                contradicts=lie if lie and query.knows(state.graph, character, lie) else None,
                uses=_uses(answers, i, trait),
            ))
        elif choice in cands or (path and choice in path):
            # Later hops of a route are not candidates yet; resolve checks each one when it is reached.
            steps.append(ActionStep(action_id=choice, uses=Uses(trait=trait) if choice.startswith("act:") and trait else Uses()))
        else:
            break
    if not steps:
        # Every guess was dropped as unsafe: talk to a person the words name, or let the moment pass.
        named = [p.id for p in scene.people if p.name in text]
        if len(named) == 1:
            steps.append(TalkStep(character=named[0], attitude=attitude_cue(text) or "polite"))
        elif any(c in cands for c in chosen):
            steps.append(ImproviseStep(target=None, approach=default_approach(state), check=False))
        else:
            return Rejected(reason=ko.NOT_ACTION)
    return Steps(steps=steps)


def questions(story: Story, state: GameState, scene: Scene, cands: dict[str, Candidate]) -> dict[str, dict]:
    """Every question a sentence could need, as if all three steps were improvised or talk; for tests and evals."""
    people = [f"talk:{p.id}" for p in scene.people][:1]
    return {**step_questions(cands), **detail_questions(story, scene, [IMPROVISE] * MAX_STEPS),
            **detail_questions(story, scene, people)}


def out_of_story(story: Story, state: GameState, text: str) -> Rejected | None:
    """Turned back without a turn: what the story says cannot happen, or a request to the game that names
    nothing in the scene. Kev's 'impossible' answer could not tell "call a dragon" from "smell the crates"."""
    if any(phrase in text for phrase in story.impossible):
        return Rejected(reason=ko.WHY_NOT["rule"])
    said = text.strip().rstrip(".!?~ ")
    if said.endswith(ko.META_ENDINGS) or any(w in said for w in ko.META_WORDS):
        scene = build(story, state)
        names = [x.name for x in [scene.place, *scene.people, *scene.items_here, *scene.carried, *scene.exits]]
        if not any(n in said for n in names):
            return Rejected(reason=ko.NOT_ACTION)
    return None


async def second_opinion(qwen, text: str, question: dict, answer: Answer) -> Answer:
    """When Kev is unsure of the first step, Qwen picks from the same closed list. On sentences no rule had
    seen, Kev alone read 19/25 right and with Qwen 22/25 (harbor holdout7); Qwen on every sentence did
    worse than Kev where Kev was sure. A Qwen failure keeps Kev's answer: the turn never waits on it."""
    if qwen is None or max(answer.probabilities.values(), default=0.0) >= SECOND_OPINION_BELOW:
        return answer
    options = list(question["criteria"].items())
    lines = "\n".join(f"{i}. {label}" for i, (_, label) in enumerate(options, 1))
    messages = [{"role": "system", "content": ko.CHOOSER},
                {"role": "user", "content": ko.fill(ko.CHOOSER_PROMPT, text=text, options=lines)}]
    try:
        reply = await qwen.pick(messages)
    except ModelUnavailable:
        return answer
    number = re.search(r"\d+", reply)
    if number is None or not 1 <= int(number[0]) <= len(options):
        return answer
    pick = options[int(number[0]) - 1][0]
    return Answer(type="choice", answer=pick, confidence=1.0, probabilities={pick: 1.0})


async def interpret(kev: KevClient, story: Story, state: GameState, text: str, qwen=None) -> Interpretation:
    """Two Kev calls at most: Kev's latency grows with the number of questions, so details are asked
    only for the steps that need them. A sentence of plain listed actions needs one call. Qwen, when
    given, settles an unsure first step."""
    refused = out_of_story(story, state, text)
    if refused is not None:
        return refused
    cands = candidates(story, state)
    questions_ = step_questions(cands)
    answers = await kev.decide(text, questions_)
    answers["s1"] = await second_opinion(qwen, text, questions_["s1"], answers["s1"])
    chosen = chosen_steps(answers, cands)
    scene = build(story, state)
    if isinstance(chosen, Clarify):
        chosen = [str(answers["s1"].answer)]  # assemble decides whether the words settle it or it is asked back
    person = addressee(text, scene)
    if person is not None and f"talk:{person}" in cands:
        # Words to a named person are talk first; whatever else Kev read in the sentence follows.
        chosen = [f"talk:{person}", *[c for c in chosen if not c.startswith("talk:") and c != IMPROVISE]][:MAX_STEPS]
    details = detail_questions(story, scene, chosen)
    if details:
        answers |= await kev.decide(text, details)
    return assemble(story, state, cands, answers, text)

