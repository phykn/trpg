"""Free text to steps: one Kev call of closed questions over the scene, then pure assembly."""

from typing import Any

from pydantic import Field

from src.content.schema import APPROACHES, RISKS, Model, Story
from src.locale import ko
from src.models.kev import Answer, KevClient
from src.rules.candidates import Candidate, candidates
from src.rules.resolve import default_approach
from src.scene.build import Scene, build
from src.scene.render import kev_state
from src.world import query
from src.world.state import ActionStep, GameState, ImproviseStep, Step, TalkStep, Uses

MAX_STEPS = 3
NONE = "none"
IMPROVISE = "improvise"
CLARIFY_FLOOR = 0.1


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


def questions(story: Story, state: GameState, scene: Scene, cands: dict[str, Candidate]) -> dict[str, dict]:
    offered = {c.id: c.label for c in cands.values() if c.kev and c.enabled and c.kind != "improvise"}
    q: dict[str, dict] = {}
    for i in range(1, MAX_STEPS + 1):
        options = {**offered, IMPROVISE: ko.IMPROVISE, NONE: ko.NONE_STEP}
        q[f"s{i}"] = _choice(ko.STEP_QUESTION.format(n=i), options)
    targets = {o.id: f"{o.name} {o.value}/{o.boxes}" for o in scene.obstacles}
    targets |= {t.id: t.name for t in scene.tags if t.kind == "snag"}
    edges = {t.id: t.name for t in scene.tags if t.kind == "edge"}
    things = {x.id: x.name for x in [*scene.carried, *scene.knowledge, *scene.skills]}
    traits = {t.id: f"{t.name}: {t.text}" for t in scene.traits}
    approaches = {a: f"{scene.approach_names[a]}: {ko.APPROACH_HINT[a]}" for a in APPROACHES}
    for i in range(1, MAX_STEPS + 1):
        detail = {
            "purpose": _choice(ko.PURPOSE_QUESTION.format(n=i), dict(ko.PURPOSES)),
            "target": _choice(ko.TARGET_QUESTION.format(n=i), {**targets, NONE: ko.NONE_OPTION}),
            "approach": _choice(ko.APPROACH_QUESTION.format(n=i), approaches),
            "risk": _choice(ko.RISK_QUESTION.format(n=i), {r: ko.RISKS[r] for r in RISKS}),
            "plausible": _choice(ko.PLAUSIBLE_QUESTION.format(n=i), dict(ko.PLAUSIBLE)),
            "check": _noul(ko.CHECK_QUESTION.format(n=i), ko.CHECK_YES, ko.CHECK_NO),
            "uses.tag": _choice(ko.USES_TAG_QUESTION.format(n=i), {**edges, NONE: ko.NONE_OPTION}),
            "uses.thing": _choice(ko.USES_THING_QUESTION.format(n=i), {**things, NONE: ko.NONE_OPTION}),
            "uses.trait": _choice(ko.USES_TRAIT_QUESTION.format(n=i), {**traits, NONE: ko.NONE_OPTION}),
        }
        for key, question in detail.items():
            if question["type"] == "noul" or len(question["criteria"]) > 1:
                q[f"s{i}.{key}"] = question
    people = scene.people
    if people:
        who = "/".join(p.name for p in people)
        topics = {t.id: f"{p.name}: {t.name}" for p in people for t in p.topics}
        lies = {
            k: f"{story.knowledge[k].title}: {story.knowledge[k].summary}"
            for p in people for k in story.characters[p.id].knows
        }
        desires = " / ".join(f"{p.name}: {story.characters[p.id].desire}" for p in people)
        fears = " / ".join(f"{p.name}: {story.characters[p.id].fear}" for p in people)
        q["talk.topic"] = _choice(ko.TOPIC_QUESTION.format(name=who), {**topics, "chat": ko.CHAT})
        q["talk.attitude"] = _choice(ko.ATTITUDE_QUESTION.format(name=who), dict(ko.ATTITUDES))
        q["talk.claim"] = _noul(ko.CLAIM_QUESTION, ko.CLAIM_YES, ko.CLAIM_NO)
        q["talk.touch"] = _choice(
            ko.TOUCH_QUESTION.format(name=who),
            {"desire": f"{ko.TOUCH['desire']} ({desires})", "fear": f"{ko.TOUCH['fear']} ({fears})",
             "none": ko.TOUCH["none"]},
        )
        if lies:
            q["talk.contradicts"] = _choice(ko.CONTRADICTS_QUESTION.format(name=who), {**lies, NONE: ko.NONE_OPTION})
    q["why_not"] = _choice(ko.WHY_NOT_QUESTION, dict(ko.WHY_NOT_OPTIONS))
    return q


def _pick(answers: dict[str, Answer], key: str, default=None):
    """Detail answers are taken at their best guess; a missing question means its only option."""
    answer = answers.get(key)
    if answer is None or answer.answer == NONE:
        return default
    return answer.answer


def _uses(answers: dict[str, Answer], i: int) -> Uses:
    return Uses(tag=_pick(answers, f"s{i}.uses.tag"), thing=_pick(answers, f"s{i}.uses.thing"),
                trait=_pick(answers, f"s{i}.uses.trait"))


def _clarify(answer: Answer, cands: dict[str, Candidate], mass_needed: float) -> Clarify | None:
    mass: dict[str, float] = {}
    for key, p in answer.probabilities.items():
        verb = key.partition(":")[0]
        mass[verb] = mass.get(verb, 0.0) + p
    if not mass:
        return None
    verb = max(mass, key=mass.get)
    if verb in (IMPROVISE, NONE) or mass[verb] < mass_needed:
        return None
    options = sorted(
        (k for k, p in answer.probabilities.items() if k.startswith(f"{verb}:") and p >= CLARIFY_FLOOR and k in cands),
        key=lambda k: -answer.probabilities[k],
    )[:3]
    return Clarify(options=[(k, cands[k].label) for k in options]) if len(options) >= 2 else None


def assemble(
    story: Story, state: GameState, cands: dict[str, Candidate], answers: dict[str, Answer], mass_needed: float
) -> Interpretation:
    first = answers["s1"]
    choice = str(first.answer)
    if first.low:
        clarify = _clarify(first, cands, mass_needed)
        if clarify is not None:
            return clarify
        choice = IMPROVISE
    elif choice == NONE:
        return Rejected(reason=ko.NOT_ACTION)
    steps: list[Step] = []
    talked = False
    for i in range(1, MAX_STEPS + 1):
        if i > 1:
            answer = answers.get(f"s{i}")
            if answer is None or answer.low or answer.answer == NONE:
                break
            choice = str(answer.answer)
        if choice == IMPROVISE:
            plausible = _pick(answers, f"s{i}.plausible", "natural")
            if plausible == "impossible":
                if i == 1:
                    return Rejected(reason=ko.WHY_NOT[_pick(answers, "why_not", "beyond")])
                break
            steps.append(ImproviseStep(
                purpose=_pick(answers, f"s{i}.purpose", "overcome"),
                target=_pick(answers, f"s{i}.target"),
                approach=_pick(answers, f"s{i}.approach", default_approach(state)),
                risk=_pick(answers, f"s{i}.risk", "normal"),
                plausibility=plausible,
                check=bool(_pick(answers, f"s{i}.check", True)),
                uses=_uses(answers, i),
            ))
        elif choice.startswith("talk:") and not talked:
            talked = True
            character = choice.partition(":")[2]
            topic = _pick(answers, "talk.topic", "chat")
            if not any(t.id == topic and t.character == character for t in story.topics):
                topic = "chat"
            lie = _pick(answers, "talk.contradicts")
            steps.append(TalkStep(
                character=character,
                topic=topic,
                attitude=_pick(answers, "talk.attitude", "polite"),
                claim=bool(_pick(answers, "talk.claim", False)),
                touch=_pick(answers, "talk.touch", "none"),
                contradicts=lie if lie and query.knows(state.graph, character, lie) else None,
                uses=_uses(answers, i),
            ))
        elif choice in cands:
            steps.append(ActionStep(action_id=choice))
        else:
            break
    if not steps:
        return Rejected(reason=ko.NOT_ACTION)
    return Steps(steps=steps)


async def interpret(kev: KevClient, story: Story, state: GameState, text: str, mass_needed: float) -> Interpretation:
    scene = build(story, state)
    cands = candidates(story, state)
    last = state.turns[-1] if state.turns else None
    answers = await kev.decide(kev_state(scene, text, last), questions(story, state, scene, cands))
    return assemble(story, state, cands, answers, mass_needed)

