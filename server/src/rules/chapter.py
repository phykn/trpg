"""What follows from the state after each step: full obstacles, danger, wounds, quests, chapters, endings."""

from src.content.schema import APPROACHES, Story
from src.locale import ko
from src.world.state import Change, GameState, Pending, TurnRecord

from . import dsl
from .candidates import open_obstacles

STALL_LIMIT = 3
APPROACH_CAP = 3


def settle(story: Story, state: GameState, record: TurnRecord) -> list[Change]:
    out: list[Change] = []
    for _ in range(8):
        before = len(out)
        for oid, o in story.obstacles.items():
            p = state.obstacles[oid]
            if p.value >= o.boxes and not p.fired:
                p.fired = True
                record.notable.append(o.name)
                dsl.apply(story, state, o.on_full, out)
        danger = story.chapter(state.chapter).danger
        if state.danger >= danger.boxes and not state.complicated:
            state.complicated = True
            out.append(Change(kind="complication", target=state.chapter))
            record.notable.append(danger.name)
            dsl.apply(story, state, danger.on_full, out)
        if state.player.wounds >= dsl.WOUND_LIMIT:
            state.player.wounds = 1
            out.append(Change(kind="downed"))
            dsl.apply(story, state, story.downed, out)
        for qid, q in story.quests.items():
            if q.chapter == state.chapter and qid not in state.quests_done and dsl.all_hold(story, state, q.done_when):
                state.quests_done.append(qid)
                out.append(Change(kind="quest", target=qid))
        if len(out) == before:
            break
    if state.ending is None:
        ending = next((e for e in story.endings if dsl.all_hold(story, state, e.when)), None)
        if ending is not None:
            state.ending = ending.id
            out.append(Change(kind="ending", target=ending.id))
    chapter = story.chapter(state.chapter)
    if state.ending is None and state.pending is None and chapter.next and dsl.all_hold(story, state, chapter.goal):
        record.recap = True
        state.pending = Pending(id=f"grow{state.turn}", kind="growth")
    return out


def after_turn(story: Story, state: GameState, record: TurnRecord) -> list[Change]:
    out: list[Change] = []
    tick = story.chapter(state.chapter).danger.tick_every
    if tick and state.turn % tick == 0 and state.ending is None:
        dsl.danger(story, state, 1, out)
    changes = [c for s in record.steps for c in s.changes] + record.changes + out
    moved = any(c.kind == "progress" and (c.after or 0) > (c.before or 0) for c in changes)
    state.stall = 0 if moved else state.stall + 1
    if state.stall >= STALL_LIMIT:
        state.stall = 0
        record.hint = hint_target(story, state)
    return out


def hint_target(story: Story, state: GameState) -> str | None:
    obstacles = open_obstacles(story, state)
    if not obstacles:
        return None
    return max(obstacles, key=lambda o: (state.obstacles[o].value / story.obstacles[o].boxes, -obstacles.index(o)))


def growth_options(story: Story, state: GameState) -> dict[str, str]:
    labels = {**ko.APPROACHES, **story.labels.approaches}
    options = {
        f"grow:approach:{a}": ko.fill(ko.LABELS["grow_approach"], name=labels[a], before=state.player.approaches[a],
                                      after=state.player.approaches[a] + 1)
        for a in APPROACHES
        if state.player.approaches[a] < APPROACH_CAP
    }
    for old in state.player.traits:
        for trait in story.traits:
            if trait.id not in state.player.traits:
                options[f"grow:trait:{old}:{trait.id}"] = ko.fill(
                    ko.LABELS["grow_trait"], old=story.trait(old).name, name=trait.name
                )
    return options


def grow(story: Story, state: GameState, option: str) -> list[Change]:
    """Apply a growth choice and enter the next chapter."""
    if option not in growth_options(story, state):
        raise ValueError("unknown growth option")
    parts = option.split(":")
    out: list[Change] = []
    if parts[1] == "approach":
        state.player.approaches[parts[2]] += 1
        out.append(Change(kind="grow", target=parts[2], after=state.player.approaches[parts[2]]))
    else:
        state.player.traits[state.player.traits.index(parts[2])] = parts[3]
        out.append(Change(kind="grow", target=parts[3]))
    state.pending = None
    dsl.enter_chapter(story, state, story.chapter(state.chapter).next, out)
    return out
