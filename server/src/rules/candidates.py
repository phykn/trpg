"""Actions the rules allow right now, keyed by an id whose prefix names the action kind."""

from dataclasses import dataclass

from src.content.schema import PLAYER, Story
from src.locale import ko
from src.world import query
from src.world.state import GameState, Tag

from .dsl import all_hold, here


@dataclass(frozen=True)
class Candidate:
    id: str
    kind: str
    label: str
    enabled: bool = True
    kev: bool = True


def tag_name(tag: Tag) -> str:
    if tag.name:
        return tag.name
    return ko.TRACES[tag.trace] if tag.trace else ko.TAG_DEFAULT[tag.kind]


def open_obstacles(story: Story, state: GameState) -> list[str]:
    place = here(state)
    return [
        oid
        for oid, o in story.obstacles.items()
        if o.place == place and state.obstacles[oid].revealed and state.obstacles[oid].value < o.boxes
    ]


def guarded(story: Story, state: GameState, item: str) -> bool:
    return any(
        item in o.guards and state.obstacles[oid].value < o.boxes for oid, o in story.obstacles.items()
    )


def candidates(story: Story, state: GameState) -> dict[str, Candidate]:
    g, place, out = state.graph, here(state), []
    name = story.name
    for dst, is_open in query.exits(g, place):
        if is_open:
            out.append(Candidate(f"move:{dst}", "move", ko.fill(ko.LABELS["move"], name=name(dst))))
    people = query.present(g, place)
    obstacles = open_obstacles(story, state)
    for cid in people:
        out.append(Candidate(f"talk:{cid}", "talk", ko.fill(ko.LABELS["talk"], name=name(cid))))
    # A carried item that reveals something stays inspectable: taking it first must not lose the clue.
    readable = [i for i in query.carried(g, PLAYER)
                if story.items[i].reveals and not query.knows(g, PLAYER, story.items[i].reveals)]
    for target in dict.fromkeys([*people, *query.items_at(g, place), *readable, *obstacles]):
        out.append(Candidate(f"inspect:{target}", "inspect", ko.fill(ko.LABELS["inspect"], name=name(target))))
    for iid in query.items_at(g, place):
        if not guarded(story, state, iid):
            out.append(Candidate(f"take:{iid}", "take", ko.fill(ko.LABELS["take"], name=name(iid))))
    for iid in query.carried(g, PLAYER):
        for cid in people:
            label = ko.fill(ko.LABELS["give"], who=name(cid), name=name(iid))
            out.append(Candidate(f"give:{cid}:{iid}", "give", label))
    for action in story.actions:
        if action.place == place and all_hold(story, state, action.show) and not (
            action.once and action.id in state.actions_done
        ):
            enabled = all_hold(story, state, action.requires)
            out.append(Candidate(f"act:{action.id}", "act", action.label, enabled=enabled))
    for oid in obstacles:
        for i, sol in enumerate(story.obstacles[oid].solutions):
            if all_hold(story, state, sol.requires):
                out.append(Candidate(f"solve:{oid}:{i}", "solve", sol.label, kev=False))
    for tag in state.tags.get(place, []):
        target = tag.target if tag.target in obstacles else (obstacles[0] if obstacles else None)
        if tag.kind == "edge" and target:
            label = ko.fill(ko.LABELS["use_tag"], tag=tag_name(tag), name=name(target))
            out.append(Candidate(f"use_tag:{tag.id}:{target}", "use_tag", label, kev=False))
    for cid in people:
        for topic in story.topics:
            if topic.character == cid and not query.knows(g, PLAYER, topic.knowledge):
                label = ko.fill(ko.LABELS["topic"], who=name(cid), name=topic.title)
                out.append(Candidate(f"topic:{cid}:{topic.id}", "topic", label, kev=False))
    out.append(Candidate("improvise", "improvise", ko.LABELS["improvise"]))
    return {c.id: c for c in out}
