"""Run one turn: up to three steps in order, stopping on a miss, then settle the world."""

from random import Random

from src.content.schema import APPROACHES, PLAYER, Story
from src.locale import ko
from src.world import query
from src.world.state import (
    ActionStep,
    Change,
    GameState,
    ImproviseStep,
    Step,
    StepResult,
    TalkStep,
    TurnRecord,
    Uses,
)

from . import dsl
from .candidates import candidates, open_obstacles
from .chapter import after_turn, settle
from .check import effect_size, modifier, risk_of, rng_for, roll, usable
from .costs import pay
from .talk import run_talk

MAX_STEPS = 3
NOTE_CHARS = 60


class Impossible(ValueError):
    pass


def approach_label(story: Story, approach: str) -> str:
    return story.labels.approaches.get(approach) or ko.APPROACHES[approach]


def best_fit(story: Story, state: GameState, obstacle: str) -> str:
    fits = story.obstacles[obstacle].fits
    return max(fits, key=lambda a: (state.player.approaches[a], -fits.index(a)))


def expand(story: Story, state: GameState, step: Step) -> Step:
    """Turn button-only ids into the improvise or talk step they stand for."""
    if not isinstance(step, ActionStep):
        return step
    kind, _, rest = step.action_id.partition(":")
    if kind == "solve":
        oid, index = rest.rsplit(":", 1)
        sol = story.obstacles[oid].solutions[int(index)]
        # The item or clue a solution needs is what the player uses: +1 to the roll, as any use is.
        needed = next((c.target for c in sol.requires if c.kind in ("carries", "knows")), None)
        return ImproviseStep(target=oid, approach=sol.approach, risk=sol.risk, label=sol.label, uses=Uses(thing=needed))
    if kind == "use_tag":
        tag, oid = rest.split(":")
        return ImproviseStep(target=oid, approach=best_fit(story, state, oid), uses=Uses(tag=tag))
    if kind == "topic":
        character, topic = rest.split(":")
        return TalkStep(character=character, topic=topic)
    return step


def possible(story: Story, state: GameState, step: Step) -> bool:
    if isinstance(step, ActionStep):
        cand = candidates(story, state).get(step.action_id)
        return cand is not None and cand.enabled and cand.kind != "improvise"
    if isinstance(step, TalkStep):
        return step.character in query.present(state.graph, dsl.here(state))
    target = step.target
    snags = [t.id for t in state.tags.get(dsl.here(state), []) if t.kind == "snag"]
    return target is None or target in open_obstacles(story, state) or target in snags


def run_action(story: Story, state: GameState, step: ActionStep, rng: Random) -> StepResult:
    kind, _, rest = step.action_id.partition(":")
    label = candidates(story, state)[step.action_id].label
    out: list[Change] = []
    result = StepResult(kind=kind, label=label, target=rest)
    if kind == "move":
        dsl.move(state, PLAYER, rest, out)
    elif kind == "inspect":
        if rest in story.obstacles:
            state.obstacles[rest].known = True
        elif rest in story.items and story.items[rest].reveals:
            dsl.learn(state, story.items[rest].reveals, out)
        out.append(Change(kind="inspect", target=rest))
    elif kind == "take":
        dsl.give(state, rest, out)
    elif kind == "give":
        character, item = rest.split(":")
        dsl.give(state, item, out, to=character)
        if item in story.characters[character].gifts:
            dsl.remember(state, character, "help", story.name(item))
            dsl.apply(story, state, story.characters[character].gifts[item], out)
    elif kind == "act":
        action = story.action(rest)
        if action.once:
            state.actions_done.append(action.id)
        effects = action.hit
        if action.check is not None:
            approach = action.check.approach
            uses = usable(story, state, None, step.uses)
            result.roll = roll(rng, modifier(story, state, approach, None, uses))
            if uses.trait:
                state.player.trait_used.append(uses.trait)
            if result.roll.grade == "miss":
                effects = action.miss
            pay(story, state, action.check.risk, result.roll.grade, None, rng, out)
        dsl.apply(story, state, effects, out)
    result.changes = out
    return result


def improvise_purpose(story: Story, step: ImproviseStep) -> str:
    obstacle = step.target in story.obstacles
    if step.target and not obstacle:
        return "clear"
    return "setup" if not obstacle and step.purpose == "overcome" else step.purpose


def improvise_label(story: Story, step: ImproviseStep) -> str:
    if step.label:
        return ko.fill(ko.SOLVE_LABEL, label=step.label, approach=approach_label(story, step.approach))
    if step.target is None and not step.check:
        return ko.LABELS["flavor"]
    obstacle = step.target in story.obstacles
    name = story.name(step.target) if obstacle else ko.TAG_DEFAULT["snag"] if step.target else ""
    return ko.fill(ko.LABELS[improvise_purpose(story, step)], approach=approach_label(story, step.approach), name=name)


def run_improvise(
    story: Story, state: GameState, step: ImproviseStep, text: str, rng: Random, notable: list[str]
) -> StepResult:
    out: list[Change] = []
    obstacle = step.target if step.target in story.obstacles else None
    snag = None if obstacle or step.target is None else dsl.find_tag(state, step.target)
    if obstacle is None and snag is None and not step.check:
        return StepResult(kind="flavor", label=ko.LABELS["flavor"])
    purpose = improvise_purpose(story, step)
    result = StepResult(kind="improvise", label=improvise_label(story, step), target=step.target or "")
    uses = usable(story, state, obstacle, step.uses)
    result.roll = roll(rng, modifier(story, state, step.approach, obstacle, uses))
    grade = result.roll.grade
    if grade != "miss":
        if purpose == "overcome":
            result.effect = effect_size(story, obstacle, step.approach, uses.tag is not None)
            dsl.progress(story, state, obstacle, result.effect, out)
            if result.effect >= 2:
                notable.append(text.strip()[:NOTE_CHARS])
        elif purpose == "setup":
            dsl.add_tag(state, "edge", obstacle, out)
        else:
            target = snag or next(
                (t for t in state.tags.get(dsl.here(state), []) if t.kind == "snag" and t.target == obstacle), None
            )
            if target is not None:
                dsl.drop_tag(state, target.id, out)
    pay(story, state, risk_of(story, step), grade, obstacle, rng, out)
    if uses.tag:
        dsl.drop_tag(state, uses.tag, out, used=True)
    if uses.trait:
        state.player.trait_used.append(uses.trait)
    result.changes = out
    return result


def resolve(story: Story, state: GameState, steps: list[Step], text: str) -> tuple[GameState, TurnRecord]:
    """Pure: the original state is untouched, whatever happens."""
    s = state.model_copy(deep=True)
    s.turn += 1
    s.revision += 1
    s.pending = None
    record = TurnRecord(n=s.turn, input=text)
    for i, raw in enumerate(steps[:MAX_STEPS]):
        step = expand(story, s, raw)
        if not possible(story, s, step):
            if i == 0:
                raise Impossible("first step is not possible")
            break
        rng = rng_for(s, i)
        if isinstance(step, ActionStep):
            result = run_action(story, s, step, rng)
        elif isinstance(step, TalkStep):
            result = run_talk(story, s, step, text, rng, record.notable)
        else:
            result = run_improvise(story, s, step, text, rng, record.notable)
        record.steps.append(result)
        record.changes.extend(settle(story, s, record))
        if (result.roll and result.roll.grade == "miss") or s.ending or s.pending:
            break
    record.changes.extend(after_turn(story, s, record))
    record.changes.extend(settle(story, s, record))
    s.graph.validate()
    return s, record


def default_approach(state: GameState) -> str:
    return max(APPROACHES, key=lambda a: (state.player.approaches[a], -APPROACHES.index(a)))
