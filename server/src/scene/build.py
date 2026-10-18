"""The part of the world the player knows. Interpretation, narration and the screen all read only this."""

from pydantic import Field

from src.content.schema import APPROACHES, PLAYER, Model, Story
from src.locale import ko
from src.rules.candidates import open_obstacles, tag_name
from src.rules.dsl import here
from src.world import query
from src.world.state import GameState


class Named(Model):
    id: str
    name: str
    text: str = ""


class Person(Model):
    id: str
    name: str
    role: str
    relation: int
    memories: list[str] = Field(default_factory=list)
    topics: list[Named] = Field(default_factory=list)
    companion: bool = False


class SceneObstacle(Model):
    id: str
    name: str
    value: int
    boxes: int
    fits: list[str] = Field(default_factory=list)


class SceneTag(Model):
    id: str
    kind: str
    name: str
    target: str | None = None
    target_name: str = ""


class Scene(Model):
    place: Named
    senses: list[str]
    exits: list[Named]
    people: list[Person]
    items_here: list[Named]
    obstacles: list[SceneObstacle]
    tags: list[SceneTag]
    traces: list[SceneTag]
    danger: Named
    danger_value: int
    danger_boxes: int
    approaches: dict[str, int]
    approach_names: dict[str, str]
    traits: list[Named]
    carried: list[Named]
    knowledge: list[Named]
    skills: list[Named]
    quests: list[Named]
    wounds: int
    gold: int


def approach_names(story: Story) -> dict[str, str]:
    return {a: story.labels.approaches.get(a) or ko.APPROACHES[a] for a in APPROACHES}


def build(story: Story, state: GameState) -> Scene:
    g, place_id, name = state.graph, here(state), story.name
    place = story.places[place_id]
    mates = set(query.companions(g))
    people = []
    for cid in query.present(g, place_id):
        c = story.characters[cid]
        topics = [
            Named(id=t.id, name=t.title)
            for t in story.topics
            if t.character == cid and not query.knows(g, PLAYER, t.knowledge)
        ]
        memories = [m["text"] for m in query.memories(g, cid)]
        people.append(Person(id=cid, name=c.name, role=c.role, relation=query.relation(g, cid),
                             memories=memories, topics=topics, companion=cid in mates))
    obstacles = [
        SceneObstacle(id=oid, name=story.obstacles[oid].name, value=state.obstacles[oid].value,
                      boxes=story.obstacles[oid].boxes,
                      fits=list(story.obstacles[oid].fits) if state.obstacles[oid].known else [])
        for oid in open_obstacles(story, state)
    ]

    def scene_tag(t) -> SceneTag:
        return SceneTag(id=t.id, kind=t.kind, name=tag_name(t), target=t.target,
                        target_name=name(t.target) if t.target else "")

    danger = story.chapter(state.chapter).danger
    return Scene(
        place=Named(id=place_id, name=place.name, text=place.text),
        senses=place.senses,
        exits=[Named(id=dst, name=name(dst), text="" if ok else "closed") for dst, ok in query.exits(g, place_id)],
        people=people,
        items_here=[Named(id=i, name=name(i), text=story.items[i].text) for i in query.items_at(g, place_id)],
        obstacles=obstacles,
        tags=[scene_tag(t) for t in state.tags.get(place_id, [])],
        traces=[scene_tag(t) for t in state.traces],
        danger=Named(id=state.chapter, name=danger.name),
        danger_value=state.danger,
        danger_boxes=danger.boxes,
        approaches=dict(state.player.approaches),
        approach_names=approach_names(story),
        traits=[Named(id=t, name=story.trait(t).name, text=story.trait(t).text) for t in state.player.traits],
        carried=[Named(id=i, name=name(i), text=story.items[i].text) for i in query.carried(g, PLAYER)],
        knowledge=[
            Named(id=k, name=story.knowledge[k].title, text=story.knowledge[k].summary)
            for k in query.known(g, PLAYER)
        ],
        skills=[Named(id=s, name=story.skills[s].name, text=story.skills[s].text) for s in state.player.skills],
        quests=[
            Named(id=q, name=story.quests[q].title, text=story.quests[q].text)
            for q in story.quests
            if story.quests[q].chapter == state.chapter and q not in state.quests_done
        ],
        wounds=state.player.wounds,
        gold=state.player.gold,
    )
