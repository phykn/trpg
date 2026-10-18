"""Free talk: topics and their reveal paths, attitudes, claims, exposure, and memories."""

from random import Random

from src.content.schema import PLAYER, Story
from src.locale import ko
from src.world import query
from src.world.state import Change, GameState, StepResult, TalkStep

from . import dsl
from .check import modifier, roll, usable
from .costs import pay

CLAIM_CHARS = 80


def relation_mod(state: GameState, character: str) -> int:
    value = query.relation(state.graph, character)
    return 1 if value >= 2 else -1 if value <= -2 else 0


def _touch(state: GameState, step: TalkStep, out: list[Change]) -> None:
    if step.touch == "desire":
        dsl.relation(state, step.character, 1, out)
    elif step.touch == "fear":
        dsl.relation(state, step.character, 1 if step.attitude == "empathy" else -1, out)


def _claim(state: GameState, step: TalkStep, text: str, out: list[Change]) -> None:
    said = text.strip()[:CLAIM_CHARS]
    state.graph.link("claimed", PLAYER, step.character, f"t{state.turn}", text=said, turn=state.turn, exposed=False)
    dsl.remember(state, step.character, "claim", said)
    out.append(Change(kind="claim", target=step.character, after=said))


def _expose(state: GameState, step: TalkStep, out: list[Change]) -> None:
    for edge in query.claims(state.graph, step.character):
        edge.props["exposed"] = True
    dsl.relation(state, step.character, -2, out)
    dsl.add_tag(state, "snag", None, out, trace="suspicion")
    dsl.remember(state, step.character, "exposed", ko.TRACES["suspicion"])
    out.append(Change(kind="exposed", target=step.character))


def run_talk(
    story: Story, state: GameState, step: TalkStep, text: str, rng: Random, notable: list[str]
) -> StepResult:
    out: list[Change] = []
    name = story.name(step.character)
    result = StepResult(kind="talk", label=ko.fill(ko.LABELS["talk"], name=name), target=step.character)
    uses = usable(story, state, None, step.uses)
    if step.claim:
        _claim(state, step, text, out)
        notable.append(text.strip()[:CLAIM_CHARS])
    lie = step.contradicts if step.claim or step.attitude == "deceive" else None
    if lie and query.knows(state.graph, step.character, lie):
        result.roll = roll(rng, modifier(story, state, "charm", None, uses, -2 + relation_mod(state, step.character)))
        if result.roll.grade == "miss":
            _expose(state, step, out)
            notable.append(ko.fill(ko.CHANGES["exposed"], name=name))
            result.changes = out
            return result
    topic = next(
        (t for t in story.topics if t.id == step.topic and t.character == step.character), None
    )
    if topic is not None and not query.knows(state.graph, PLAYER, topic.knowledge):
        result.label = ko.fill(ko.LABELS["topic"], who=name, name=topic.title)
        if any(dsl.all_hold(story, state, alt) for alt in topic.free_when):
            dsl.learn(state, topic.knowledge, out)
        else:
            approach = "force" if step.attitude == "threaten" else "charm"
            extra = topic.mods.get(step.attitude, 0) + relation_mod(state, step.character)
            result.roll = roll(rng, modifier(story, state, approach, None, uses, extra))
            if result.roll.grade != "miss":
                dsl.learn(state, topic.knowledge, out)
            risk = "normal" if step.attitude == "threaten" else "low"
            pay(story, state, risk, result.roll.grade, None, rng, out, partner=step.character)
    if step.attitude == "threaten":
        dsl.relation(state, step.character, -1, out)
        dsl.remember(state, step.character, "threat", text.strip()[:CLAIM_CHARS])
    _touch(state, step, out)
    if result.roll and uses.trait:
        state.player.trait_used.append(uses.trait)
    if result.roll and uses.tag:
        dsl.drop_tag(state, uses.tag, out, used=True)
    result.changes = out
    return result
