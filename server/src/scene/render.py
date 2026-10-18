"""Scene as text: Kev's state, the narrator's fact list, and journal lines for changes."""

from src.content.schema import Story
from src.locale import ko
from src.world.state import Change, GameState, TurnRecord

from .build import Scene


def _join(items, fmt=lambda x: x.name) -> str:
    return ", ".join(fmt(x) for x in items) or "-"


def kev_state(scene: Scene, text: str, last: TurnRecord | None = None) -> str:
    lines = [
        f"장소: {scene.place.name}. {scene.place.text}",
        f"출구: {_join([e for e in scene.exits if not e.text])}",
        f"인물: {_join(scene.people, lambda p: f'{p.name}({p.role})')}",
        f"보이는 물건: {_join(scene.items_here)}",
        f"장애물: {_join(scene.obstacles, lambda o: f'{o.name} {o.value}/{o.boxes}')}",
        f"장면 상황: {_join(scene.tags, lambda t: f'{t.name}({ko.TAG_DEFAULT[t.kind]})')}",
        f"당신의 특성: {_join(scene.traits)}",
        f"지닌 것: {_join(scene.carried)}",
        f"아는 것: {_join(scene.knowledge)}",
    ]
    if last is not None and last.input:
        lines.append(f"직전 행동: {last.input}")
    lines.append(f"플레이어 입력: {text}")
    return "\n".join(lines)


def tag_label(kind: str, name, names: dict[str, str], tag_id: str) -> str:
    if names.get(tag_id):
        return names[tag_id]
    if name:
        return str(name)
    return ko.TRACES.get(kind) or ko.TAG_DEFAULT.get(kind, "")


def change_line(story: Story, state: GameState, c: Change, names: dict[str, str] | None = None) -> str:
    names = names or {}
    template = ko.CHANGES[c.kind]
    if not template:
        return ""
    if c.kind == "progress":
        return ko.fill(template, name=story.name(c.target), before=c.before, after=c.after,
                       boxes=story.obstacles[c.target].boxes)
    if c.kind == "danger":
        danger = story.chapter(state.chapter).danger
        return ko.fill(template, name=danger.name, before=c.before, after=c.after, boxes=danger.boxes)
    if c.kind in ("tag_add", "tag_use", "tag_drop"):
        return ko.fill(template, name=tag_label(str(c.before), c.after, names, c.target))
    if c.kind in ("relation", "gold", "wound"):
        return ko.fill(template, name=story.name(c.target), before=c.before, after=c.after)
    if c.kind == "move":
        if c.target == "player":
            return ko.fill(ko.CHANGES["go"], name=story.name(str(c.after)))
        if c.after is None:
            return ko.fill(ko.CHANGES["leave"], name=story.name(c.target))
        return ko.fill(template, name=story.name(c.target), after=story.name(str(c.after)))
    if c.kind == "complication":
        return ko.fill(template, name=story.chapter(c.target).danger.name)
    if c.kind == "chapter":
        return ko.fill(template, name=story.chapter(str(c.after)).title)
    if c.kind == "ending":
        return ko.fill(template, name=next(e.title for e in story.endings if e.id == c.target))
    if c.kind == "quest":
        return ko.fill(template, name=story.quests[c.target].title)
    if c.kind == "grow":
        approach = story.labels.approaches.get(c.target) or ko.APPROACHES.get(c.target)
        return ko.fill(template, name=approach or story.trait(c.target).name)
    return ko.fill(template, name=story.name(c.target))


def record_lines(story: Story, state: GameState, record: TurnRecord) -> list[str]:
    lines = []
    for step in record.steps:
        roll = ""
        if step.roll:
            r = step.roll
            roll = " · " + ko.fill(ko.ROLL, a=r.dice[0], b=r.dice[1], mod=r.modifier, total=r.total,
                                   grade=ko.GRADES[r.grade])
        lines.append(step.label + roll)
        lines += [change_line(story, state, c, record.tag_names) for c in step.changes]
    lines += [change_line(story, state, c, record.tag_names) for c in record.changes]
    return [line for line in lines if line]


def facts(story: Story, state: GameState, scene: Scene) -> list[str]:
    out = [
        f"장소: {scene.place.name}. {scene.place.text}",
        f"감각: {', '.join(scene.senses)}",
        f"출구: {_join(scene.exits, lambda e: e.name + (' (닫힘)' if e.text else ''))}",
    ]
    for p in scene.people:
        c = story.characters[p.id]
        memo = f" 기억: {' / '.join(p.memories[-3:])}" if p.memories else ""
        out.append(f"인물: {p.name}({p.role}), 관계 {p.relation:+d}. 말투: {c.voice} 바람: {c.desire} "
                   f"두려움: {c.fear} 지키는 선: {c.boundary}{memo}")
    out += [
        f"보이는 물건: {_join(scene.items_here)}",
        f"장애물: {_join(scene.obstacles, lambda o: f'{o.name} {o.value}/{o.boxes}')}",
        f"장면 상황: {_join(scene.tags + scene.traces)}",
        f"위험: {scene.danger.name} {scene.danger_value}/{scene.danger_boxes}",
        f"당신이 지닌 것: {_join(scene.carried)}",
        f"당신이 아는 것: {_join(scene.knowledge, lambda k: f'{k.name}: {k.text}')}",
        f"당신의 특성: {_join(scene.traits, lambda t: f'{t.name}({t.text})')}",
    ]
    return out
