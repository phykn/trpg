import pytest
from src.content.load import new_game
from src.content.schema import Chapter, Condition, Danger, Effect, Place
from src.rules import dsl
from src.rules.chapter import grow, growth_options, settle
from src.rules.resolve import resolve
from src.world.state import ActionStep, TurnRecord


def test_danger_full_complicates_once(story, state):
    state.danger = 6
    record = TurnRecord(n=1)
    changes = settle(story, state, record)
    assert [c.kind for c in changes].count("complication") == 1
    assert state.flags["storm"] is True
    assert settle(story, state, record) == []


def test_downed_moves_back_and_resets_wounds(story, state):
    out = []
    dsl.move(state, "player", "base", out)
    state.player.wounds = 3
    changes = settle(story, state, TurnRecord(n=1))
    assert "downed" in [c.kind for c in changes]
    assert state.player.wounds == 1
    assert state.graph.edge("at", "player", "square")


def test_endings_follow_story_order(story, state):
    state.flags["lit"] = True
    settle(story, state, TurnRecord(n=1))
    assert state.ending == "calm"


def test_tick_every_raises_danger(story, state):
    for _ in range(4):
        state, _ = resolve(story, state, [ActionStep(action_id="inspect:mira")], "본다")
    assert state.danger == 1


def test_stall_gives_a_hint(story, state):
    state, _ = resolve(story, state, [ActionStep(action_id="move:base")], "간다")
    records = []
    for _ in range(2):
        state, r = resolve(story, state, [ActionStep(action_id="inspect:door")], "본다")
        records.append(r)
    assert records[-1].hint == "door"
    assert state.obstacles["door"].known


@pytest.fixture
def two_chapters(story):
    story = story.model_copy(deep=True)
    story.places["dock"] = Place(name="부두", text="배가 닿는 곳", chapter="ch_two", senses=["a", "b", "c"])
    story.chapters[0].next = "ch_two"
    story.chapters.append(Chapter(
        id="ch_two", title="둘째 장", place="dock",
        danger=Danger(name="밀물", boxes=6, on_full=[Effect(kind="danger", value=0)]),
        goal=[Condition(kind="at", target="dock")],
    ))
    return story


def test_goal_opens_growth_then_next_chapter(two_chapters):
    state = new_game(two_chapters, game_id="g", seed=1)
    state.flags["lit"] = True
    record = TurnRecord(n=1)
    settle(two_chapters, state, record)
    assert state.ending is None or state.ending == "calm"
    state.ending = None
    state.pending = None
    record = TurnRecord(n=1)
    two_chapters.endings[0].when.append(Condition(kind="chapter", target="ch_two"))
    two_chapters.endings[1].when.append(Condition(kind="chapter", target="ch_two"))
    settle(two_chapters, state, record)
    assert record.recap and state.pending.kind == "growth"
    options = growth_options(two_chapters, state)
    assert "grow:approach:force" in options
    out = []
    dsl.add_tag(state, "snag", None, out, trace="wanted")
    changes = grow(two_chapters, state, "grow:approach:force")
    assert state.player.approaches["force"] == 1
    assert state.chapter == "ch_two" and state.traces == [] and state.danger == 0
    assert state.graph.edge("at", "player", "dock")
    assert {c.kind for c in changes} >= {"grow", "chapter", "move"}
    with pytest.raises(ValueError):
        grow(two_chapters, state, "grow:approach:nothing")
