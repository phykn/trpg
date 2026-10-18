"""The client's GameView and the confirm card for high-risk steps."""

from pydantic import Field

from src.content.schema import APPROACHES, Model, Story
from src.locale import ko
from src.rules.candidates import candidates
from src.rules.chapter import growth_options
from src.rules.check import modifier, odds, risk_of, usable
from src.rules.costs import TABLE
from src.rules.recommend import recommend
from src.rules.resolve import expand, improvise_label
from src.world.state import GameState, ImproviseStep, Step, TalkStep

from .build import Named, build
from .render import record_lines

JOURNAL_TURNS = 30


class Button(Model):
    id: str
    label: str
    enabled: bool = True


class Card(Model):
    id: str
    steps: list[str]
    odds: tuple[float, float, float]
    costs: list[str]


class PendingView(Model):
    kind: str
    card: Card | None = None
    options: list[Button] = Field(default_factory=list)


class Meter(Model):
    id: str
    name: str
    value: int
    boxes: int
    fits: list[str] = Field(default_factory=list)


class Chip(Model):
    id: str
    name: str
    kind: str
    target: str = ""


class Person(Model):
    id: str
    name: str
    role: str
    mood: str


class Journal(Model):
    n: int
    input: str
    lines: list[str]
    narration: str | None = None


class Player(Model):
    approaches: list[Meter]
    traits: list[Named]
    wounds: int
    gold: int
    items: list[Named]
    knowledge: list[Named]
    skills: list[Named]


class GameView(Model):
    game_id: str
    revision: int
    turn: int
    title: str
    chapter: str
    intro: str
    place: Named
    senses: list[str]
    exits: list[Button]
    people: list[Person]
    obstacles: list[Meter]
    danger: Meter
    tags: list[Chip]
    player: Player
    quests: list[Named]
    buttons: list[Button]
    journal: list[Journal]
    pending: PendingView | None = None
    ending: Named | None = None
    narrated: bool = False


def mood(relation: int) -> str:
    return ko.MOODS[max(-2, min(2, relation))]


def confirm_card(story: Story, state: GameState, steps: list[Step], card_id: str) -> Card | None:
    """A card when any step is a high-risk improvise; None when the turn can run at once."""
    risky = None
    labels = []
    for raw in steps:
        step = expand(story, state, raw)
        if isinstance(step, ImproviseStep):
            labels.append(improvise_label(story, step))
            if step.check and risk_of(story, step) == "high" and risky is None:
                risky = step
        elif isinstance(step, TalkStep):
            labels.append(ko.fill(ko.LABELS["talk"], name=story.name(step.character)))
        else:
            cand = candidates(story, state).get(step.action_id)
            labels.append(cand.label if cand else step.action_id)
    if risky is None:
        return None
    target = risky.target if risky.target in story.obstacles else None
    mod = modifier(story, state, risky.approach, target, usable(story, state, target, risky.uses))
    costs = [
        f"{ko.GRADES[grade]}: " + ", ".join(ko.fill(ko.COSTS[what], n=n) for what, n in TABLE[("high", grade)])
        for grade in ("mixed", "miss")
    ]
    return Card(id=card_id, steps=labels, odds=odds(mod), costs=costs)


def game_view(story: Story, state: GameState, intro: str = "") -> GameView:
    scene = build(story, state)
    names = {k: v for r in state.turns for k, v in r.tag_names.items()}
    pending = None
    if state.pending and state.pending.kind == "growth":
        options = [Button(id=k, label=v) for k, v in growth_options(story, state).items()]
        pending = PendingView(kind="growth", options=options)
    elif state.pending:
        card = confirm_card(story, state, state.pending.steps, state.pending.id)
        pending = PendingView(kind="confirm", card=card)
    ending = next((Named(id=e.id, name=e.title, text=e.text) for e in story.endings if e.id == state.ending), None)
    last = state.turns[-1] if state.turns else None
    buttons = [] if pending or ending else [
        Button(id=c.id, label=c.label) for c in recommend(story, state, last.hint if last else None)
    ]
    return GameView(
        game_id=state.game_id,
        revision=state.revision,
        turn=state.turn,
        title=story.title,
        chapter=story.chapter(state.chapter).title,
        intro=intro or story.intro,
        place=scene.place,
        senses=scene.senses,
        exits=[Button(id=f"move:{e.id}", label=e.name, enabled=not e.text) for e in scene.exits],
        people=[Person(id=p.id, name=p.name, role=p.role, mood=mood(p.relation)) for p in scene.people],
        obstacles=[Meter(id=o.id, name=o.name, value=o.value, boxes=o.boxes,
                         fits=[scene.approach_names[a] for a in o.fits]) for o in scene.obstacles],
        danger=Meter(id=scene.danger.id, name=scene.danger.name, value=scene.danger_value, boxes=scene.danger_boxes),
        tags=[Chip(id=t.id, name=names.get(t.id) or t.name, kind=t.kind, target=t.target_name)
              for t in scene.tags + scene.traces],
        player=Player(
            approaches=[Meter(id=a, name=scene.approach_names[a], value=scene.approaches[a], boxes=3) for a in APPROACHES],
            traits=scene.traits, wounds=scene.wounds, gold=scene.gold,
            items=scene.carried, knowledge=scene.knowledge, skills=scene.skills,
        ),
        quests=scene.quests,
        buttons=buttons,
        journal=[
            Journal(n=r.n, input=r.input, lines=record_lines(story, state, r), narration=r.narration)
            for r in state.turns[-JOURNAL_TURNS:]
        ],
        pending=pending,
        ending=ending,
        narrated=bool(last and last.narration),
    )
