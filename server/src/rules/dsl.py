"""Conditions, state operations, and authored effects. Every state change goes through an op here."""

from src.content.schema import PLAYER, Condition, Effect, Story, TagKind, TagLife, Trace
from src.world import query
from src.world.state import Change, GameState, Tag

MAX_TAGS = 6
MEMORY_LIMIT = 5
WOUND_LIMIT = 3


def _compare(left, op: str, right) -> bool:
    if op == "eq":
        return left == right
    if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
        return False
    return left >= right if op == "gte" else left < right


def holds(story: Story, state: GameState, cond: Condition) -> bool:
    g, kind, op = state.graph, cond.kind, cond.op
    if kind == "at":
        result = query.place_of(g, cond.source) == cond.target
    elif kind == "knows":
        result = query.knows(g, cond.source, cond.target)
    elif kind == "carries":
        result = cond.target in query.carried(g, cond.source)
    elif kind == "relation":
        result = _compare(query.relation(g, cond.target), op or "gte", cond.value)
    elif kind == "flag":
        default = 0 if isinstance(cond.value, int) and not isinstance(cond.value, bool) else False
        result = _compare(state.flags.get(cond.target, default), op or "eq", cond.value)
    elif kind == "progress":
        value = state.obstacles[cond.target].value
        need = story.obstacles[cond.target].boxes if cond.value == "full" else cond.value
        result = _compare(value, op or "gte", need)
    elif kind == "trace":
        result = any(t.trace == cond.target for t in state.traces)
    elif kind == "quest":
        result = cond.target in state.quests_done
    elif kind == "turn":
        result = _compare(state.turn, op or "gte", cond.value)
    elif kind == "gold":
        result = _compare(state.player.gold, op or "gte", cond.value)
    else:
        result = state.chapter == cond.target
    return result != cond.negate


def all_hold(story: Story, state: GameState, conds: list[Condition]) -> bool:
    return all(holds(story, state, c) for c in conds)


def here(state: GameState) -> str:
    place = query.place_of(state.graph, PLAYER)
    assert place is not None
    return place


def set_flag(state: GameState, name: str, value, out: list[Change], add: bool = False) -> None:
    before = state.flags.get(name, 0 if add else None)
    state.flags[name] = (before or 0) + value if add else value
    out.append(Change(kind="flag", target=name, before=before, after=state.flags[name]))


def learn(state: GameState, knowledge: str, out: list[Change]) -> None:
    if not query.knows(state.graph, PLAYER, knowledge):
        state.graph.link("knows", PLAYER, knowledge)
        out.append(Change(kind="learn", target=knowledge))


def _detach(state: GameState, node_id: str) -> None:
    for edge in state.graph.into(node_id, "carries") + state.graph.out(node_id, "at"):
        state.graph.unlink(edge.id)


def give(state: GameState, item: str, out: list[Change], to: str = PLAYER) -> None:
    if query.holder(state.graph, item) == to:
        return
    _detach(state, item)
    state.graph.link("carries", to, item)
    out.append(Change(kind="gain" if to == PLAYER else "lose", target=item, after=to))


def take(state: GameState, item: str, out: list[Change]) -> None:
    if query.holder(state.graph, item) == PLAYER:
        _detach(state, item)
        out.append(Change(kind="lose", target=item))


def move(state: GameState, who: str, place: str, out: list[Change]) -> None:
    before = query.place_of(state.graph, who)
    if before == place:
        return
    _detach(state, who)
    if place:
        state.graph.link("at", who, place)
    out.append(Change(kind="move", target=who, before=before, after=place or None))
    if who == PLAYER:
        for mate in query.companions(state.graph):
            if query.place_of(state.graph, mate) != place:
                _detach(state, mate)
                state.graph.link("at", mate, place)
        if before:
            for tag in [t for t in state.tags.get(before, []) if t.life == "scene"]:
                drop_tag(state, tag.id, out)


def companion(state: GameState, character: str, join: bool, out: list[Change]) -> None:
    edge = state.graph.edge("companion", PLAYER, character)
    if join and edge is None:
        state.graph.link("companion", PLAYER, character)
        move(state, character, here(state), out)
    elif not join and edge is not None:
        state.graph.unlink(edge.id)
    else:
        return
    out.append(Change(kind="companion", target=character, after=int(join)))


def relation(state: GameState, character: str, delta: int, out: list[Change]) -> None:
    edge = query.relation_edge(state.graph, character)
    if edge is None or delta == 0:
        return
    before = int(edge.props.get("value", 0))
    edge.props["value"] = max(-3, min(3, before + delta))
    if edge.props["value"] != before:
        out.append(Change(kind="relation", target=character, before=before, after=edge.props["value"]))


def remember(state: GameState, character: str, kind: str, text: str) -> None:
    edge = query.relation_edge(state.graph, character)
    if edge is not None:
        memories = [*edge.props.get("memories", []), {"turn": state.turn, "kind": kind, "text": text}]
        edge.props["memories"] = memories[-MEMORY_LIMIT:]


def set_exit(state: GameState, src: str, dst: str, is_open: bool, out: list[Change]) -> None:
    for a, b in ((src, dst), (dst, src)):
        edge = state.graph.edge("connects", a, b)
        if edge is not None and edge.props.get("open", True) != is_open:
            edge.props["open"] = is_open
            out.append(Change(kind="open" if is_open else "close", target=b, before=a))


def add_tag(
    state: GameState,
    kind: TagKind,
    target: str | None,
    out: list[Change],
    *,
    life: TagLife = "scene",
    trace: Trace | None = None,
    name: str = "",
) -> Tag:
    made = sum(t.turn == state.turn for ts in [*state.tags.values(), state.traces] for t in ts)
    tag = Tag(
        id=f"t{state.turn}_{made + 1}", kind=kind, target=target,
        life="chapter" if trace else life, trace=trace, name=name, turn=state.turn,
    )
    if tag.life == "chapter":
        state.traces = [t for t in state.traces if t.trace != trace or trace is None] + [tag]
    else:
        place = here(state)
        state.tags.setdefault(place, []).append(tag)
        while len(state.tags[place]) > MAX_TAGS:
            drop_tag(state, state.tags[place][0].id, out)
    out.append(Change(kind="tag_add", target=tag.id, before=tag.trace or kind, after=name))
    return tag


def find_tag(state: GameState, tag_id: str) -> Tag | None:
    for tag in [t for ts in state.tags.values() for t in ts] + state.traces:
        if tag.id == tag_id:
            return tag
    return None


def drop_tag(state: GameState, tag_id: str, out: list[Change], used: bool = False) -> None:
    tag = find_tag(state, tag_id)
    if tag is None:
        return
    for place, tags in state.tags.items():
        state.tags[place] = [t for t in tags if t.id != tag_id]
    state.traces = [t for t in state.traces if t.id != tag_id]
    out.append(Change(kind="tag_use" if used else "tag_drop", target=tag_id, before=tag.kind, after=tag.name))


def progress(story: Story, state: GameState, obstacle: str, delta: int, out: list[Change]) -> None:
    p = state.obstacles[obstacle]
    before, p.value = p.value, max(0, min(story.obstacles[obstacle].boxes, p.value + delta))
    if p.value != before:
        out.append(Change(kind="progress", target=obstacle, before=before, after=p.value))


def danger(story: Story, state: GameState, delta: int, out: list[Change]) -> None:
    boxes = story.chapter(state.chapter).danger.boxes
    before, state.danger = state.danger, max(0, min(boxes, state.danger + delta))
    if state.danger != before:
        out.append(Change(kind="danger", before=before, after=state.danger))


def gold(state: GameState, delta: int, out: list[Change]) -> None:
    before, state.player.gold = state.player.gold, max(0, state.player.gold + delta)
    if state.player.gold != before:
        out.append(Change(kind="gold", before=before, after=state.player.gold))


def wound(state: GameState, delta: int, out: list[Change]) -> None:
    before = state.player.wounds
    state.player.wounds = max(0, min(WOUND_LIMIT, before + delta))
    if state.player.wounds != before:
        out.append(Change(kind="wound", before=before, after=state.player.wounds))


def reveal(state: GameState, obstacle: str, out: list[Change]) -> None:
    if not state.obstacles[obstacle].revealed:
        state.obstacles[obstacle].revealed = True
        out.append(Change(kind="reveal", target=obstacle))


def enter_chapter(story: Story, state: GameState, chapter: str, out: list[Change]) -> None:
    before = state.chapter
    state.chapter, state.danger, state.complicated = chapter, 0, False
    state.traces = []
    state.player.trait_used = []
    out.append(Change(kind="chapter", before=before, after=chapter))
    if story.chapter(chapter).place:
        move(state, PLAYER, story.chapter(chapter).place, out)


def apply(story: Story, state: GameState, effects: list[Effect], out: list[Change]) -> None:
    for e in effects:
        k = e.kind
        if k in ("flag", "flag_add"):
            set_flag(state, e.target, e.value, out, add=k == "flag_add")
        elif k == "learn":
            learn(state, e.target, out)
        elif k == "give":
            give(state, e.target, out, to=e.source)
        elif k == "take":
            take(state, e.target, out)
        elif k == "move":
            move(state, e.source, e.target, out)
        elif k == "companion":
            companion(state, e.target, bool(e.value), out)
        elif k == "relation":
            relation(state, e.target, int(e.value), out)
        elif k in ("open", "close"):
            set_exit(state, e.source, e.target, k == "open", out)
        elif k == "tag":
            trace = e.key if e.key in ("wanted", "suspicion", "reputation") else None
            kind = "edge" if e.key in ("edge", "reputation") else "snag"
            add_tag(state, kind, e.target or None, out, trace=trace, name=str(e.value) if e.value is not True else "")
        elif k == "reveal":
            reveal(state, e.target, out)
        elif k == "progress":
            progress(story, state, e.target, int(e.value), out)
        elif k == "danger":
            danger(story, state, int(e.value), out)
        elif k == "gold":
            gold(state, int(e.value), out)
        elif k == "chapter":
            enter_chapter(story, state, e.target, out)
        elif k == "ending" and state.ending is None:
            state.ending = e.target
            out.append(Change(kind="ending", target=e.target))
