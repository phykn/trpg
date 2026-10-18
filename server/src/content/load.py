"""Read a story folder and build the opening game state from it."""

from dataclasses import dataclass
from pathlib import Path

from src.world.graph import Graph
from src.world.state import GameState, Progress, Sheet, TurnRecord

from .schema import APPROACHES, PLAYER, Approach, Story

START_SPREAD = [0, 1, 1, 2]


@dataclass(frozen=True)
class Loaded:
    story: Story
    style: str
    folder: Path


def load_story(folder: Path) -> Loaded:
    story = Story.model_validate_json((folder / "scenario.json").read_text(encoding="utf-8"))
    style_path = folder / "world.md"
    style = style_path.read_text(encoding="utf-8") if style_path.is_file() else ""
    return Loaded(story=story, style=style, folder=folder)


def story_folders(root: Path) -> list[Path]:
    return sorted(p for p in root.iterdir() if (p / "scenario.json").is_file())


def check_creation(story: Story, approaches: dict[Approach, int], traits: list[str]) -> None:
    if sorted(approaches.get(a, 0) for a in APPROACHES) != START_SPREAD or set(approaches) - set(APPROACHES):
        raise ValueError("approaches must spread +2, +1, +1, 0")
    known = {t.id for t in story.traits}
    if len(traits) != 2 or len(set(traits)) != 2 or not set(traits) <= known:
        raise ValueError("pick two different traits from the story")


def initial_graph(story: Story) -> Graph:
    g = Graph()
    for pid in story.places:
        g.add_node(pid, "place")
    for cid in story.characters:
        g.add_node(cid, "character")
    for iid in story.items:
        g.add_node(iid, "item")
    for kid in story.knowledge:
        g.add_node(kid, "knowledge")
    for sid in story.skills:
        g.add_node(sid, "skill")
    for qid in story.quests:
        g.add_node(qid, "quest")
    g.add_node(PLAYER, "character")
    for pid, place in story.places.items():
        for ex in place.exits:
            g.link("connects", pid, ex.to, open=ex.open)
    g.link("at", PLAYER, story.start.place)
    for cid, c in story.characters.items():
        place = c.place or (story.start.place if c.companion else "")
        if place:
            g.link("at", cid, place)
        for kid in c.knows:
            g.link("knows", cid, kid)
        g.link("relation", cid, PLAYER, value=c.relation, memories=[])
        if c.companion:
            g.link("companion", PLAYER, cid)
    for iid, item in story.items.items():
        if item.holder:
            g.link("carries", item.holder, iid)
        elif item.place:
            g.link("at", iid, item.place)
    for iid in story.start.items:
        if not g.into(iid, "carries"):
            g.link("carries", PLAYER, iid)
    for kid in story.start.knows:
        g.link("knows", PLAYER, kid)
    g.validate()
    return g


def new_game(
    story: Story,
    *,
    game_id: str,
    seed: int,
    approaches: dict[Approach, int] | None = None,
    traits: list[str] | None = None,
) -> GameState:
    if story.creation.choose and approaches is not None and traits is not None:
        check_creation(story, approaches, traits)
    else:
        approaches, traits = dict(story.creation.approaches), list(story.creation.traits)
    return GameState(
        game_id=game_id,
        story_id=story.id,
        story_version=story.version,
        seed=seed,
        graph=initial_graph(story),
        player=Sheet(
            approaches={a: approaches.get(a, 0) for a in APPROACHES},
            traits=traits,
            skills=list(story.start.skills),
            gold=story.start.gold,
        ),
        chapter=story.start.chapter,
        obstacles={oid: Progress(revealed=not o.hidden) for oid, o in story.obstacles.items()},
        turns=[TurnRecord(n=0, input="")],
    )
