import pytest
from src.content.schema import Condition, Cost, Effect
from src.rules import dsl
from src.rules.candidates import candidates
from src.rules.check import effect_size, modifier, odds, risk_of
from src.rules.costs import pay
from src.rules.recommend import recommend
from src.rules.resolve import Impossible, resolve
from src.world.state import ActionStep, ImproviseStep, TalkStep, Uses


def at_base(story, state):
    out = []
    dsl.move(state, "player", "base", out)
    return state


def test_conditions(story, state):
    assert dsl.holds(story, state, Condition(kind="at", target="square"))
    assert dsl.holds(story, state, Condition(kind="relation", target="doha", value=1))
    assert not dsl.holds(story, state, Condition(kind="relation", target="doha", value=2))
    assert dsl.holds(story, state, Condition(kind="flag", target="lit", value=True, negate=True))
    assert not dsl.holds(story, state, Condition(kind="progress", target="door", value="full"))
    assert dsl.holds(story, state, Condition(kind="turn", value=0))
    assert dsl.holds(story, state, Condition(kind="chapter", target="ch_light"))


def test_effects_change_state_and_report(story, state):
    out = []
    dsl.apply(story, state, [
        Effect(kind="open", source="base", target="top"),
        Effect(kind="flag_add", target="noise", value=2),
        Effect(kind="relation", target="mira", value=9),
        Effect(kind="give", target="spare_key"),
        Effect(kind="companion", target="doha"),
    ], out)
    assert state.graph.edge("connects", "base", "top").props["open"] is True
    assert state.flags["noise"] == 2
    assert state.graph.edge("relation", "mira", "player").props["value"] == 3
    assert "spare_key" in [e.dst for e in state.graph.out("player", "carries")]
    assert {c.kind for c in out} >= {"open", "flag", "relation", "gain", "companion"}
    dsl.move(state, "player", "base", out)
    assert state.graph.edge("at", "doha", "base"), "companions follow the player"


def test_leaving_drops_scene_tags_but_keeps_traces(story, state):
    out = []
    dsl.add_tag(state, "edge", None, out)
    dsl.add_tag(state, "snag", None, out, trace="wanted")
    dsl.move(state, "player", "base", out)
    assert state.tags["square"] == []
    assert [t.trace for t in state.traces] == ["wanted"]


def test_tag_cap(story, state):
    out = []
    for _ in range(8):
        dsl.add_tag(state, "edge", None, out)
    assert len(state.tags["square"]) == dsl.MAX_TAGS


def test_candidates_hide_closed_exits_and_mark_button_only(story, state):
    state = at_base(story, state)
    cands = candidates(story, state)
    assert "move:top" not in cands
    assert {c.id for c in cands.values() if not c.kev} == {"solve:door:1", "solve:door:2"}
    assert "solve:door:0" not in cands, "the key solution needs the key"


def test_guarded_items_cannot_be_taken(story, state):
    story = story.model_copy(deep=True)
    story.obstacles["lamp"].place = "square"
    story.obstacles["lamp"].guards = ["bread"]
    assert "take:bread" not in candidates(story, state)


def test_odds_and_modifiers(story, state):
    assert sum(odds(0)) == pytest.approx(1)
    assert odds(3)[0] > odds(0)[0]
    out = []
    edge = dsl.add_tag(state, "edge", None, out)
    for _ in range(3):
        dsl.add_tag(state, "snag", None, out)
    uses = Uses(tag=edge.id)
    assert modifier(story, state, "finesse", None, uses) == 2 + 1 - 2
    assert effect_size(story, "door", "wits", True) == 3
    assert effect_size(story, "door", "force", False) == 1
    assert risk_of(story, ImproviseStep(target="door", approach="charm", risk="normal")) == "high"
    assert risk_of(story, ImproviseStep(target="door", approach="wits", plausibility="stretch")) == "high"


@pytest.mark.parametrize(("risk", "grade", "danger"), [
    ("low", "hit", 0), ("low", "mixed", 1), ("normal", "miss", 1), ("high", "mixed", 1), ("high", "miss", 2),
])
def test_cost_table(story, state, risk, grade, danger):
    from random import Random
    out = []
    pay(story, state, risk, grade, "door", Random(1), out)
    assert state.danger == danger


def test_loss_with_nothing_to_pay_raises_danger(story, state):
    from random import Random
    story = story.model_copy(deep=True)
    story.obstacles["door"].costs = [Cost(kind="gold", value=1)]
    state.player.gold = 0
    out = []
    pay(story, state, "high", "mixed", "door", Random(1), out)
    assert state.danger == 2


def test_first_impossible_step_leaves_state_untouched(story, state):
    before = state.model_dump()
    with pytest.raises(Impossible):
        resolve(story, state, [ActionStep(action_id="move:top")], "올라간다")
    assert state.model_dump() == before


def test_same_seed_same_result(story, state):
    steps = [ActionStep(action_id="move:base"), ActionStep(action_id="solve:door:2")]
    a, ra = resolve(story, state, steps, "문을 딴다")
    b, rb = resolve(story, state, steps, "문을 딴다")
    assert ra == rb and a == b


def test_chain_stops_after_a_miss(story, state):
    for seed in range(40):
        state.seed = seed
        steps = [ActionStep(action_id="move:base"), ActionStep(action_id="solve:door:1"),
                 ActionStep(action_id="move:square")]
        _, record = resolve(story, state, steps, "문을 비틀고 돌아온다")
        if record.steps[1].roll.grade == "miss":
            assert len(record.steps) == 2
            return
    pytest.fail("no miss in 40 seeds")


def test_improvise_overcome_setup_clear_and_flavor(story, state):
    state = at_base(story, state)
    out = []
    snag = dsl.add_tag(state, "snag", "door", out)
    s, r = resolve(story, state, [ImproviseStep(purpose="clear", target=snag.id, approach="wits")], "녹을 닦는다")
    if r.steps[0].roll.grade != "miss":
        assert all(t.id != snag.id for t in s.tags["base"])
    s, r = resolve(story, state, [ImproviseStep(purpose="setup", target="door", approach="wits")], "기름을 바른다")
    if r.steps[0].roll.grade != "miss":
        assert any(t.kind == "edge" and t.target == "door" for t in s.tags["base"])
    s, r = resolve(story, state, [ImproviseStep(target=None, approach="wits", check=False)], "하늘을 본다")
    assert r.steps[0].kind == "flavor" and r.steps[0].roll is None


def test_using_an_edge_consumes_it(story, state):
    state = at_base(story, state)
    out = []
    edge = dsl.add_tag(state, "edge", "door", out)
    s, r = resolve(story, state, [ActionStep(action_id=f"use_tag:{edge.id}:door")], "틈을 이용한다")
    assert all(t.id != edge.id for t in s.tags.get("base", []))
    assert r.steps[0].kind == "improvise"


def test_full_obstacle_fires_once_and_opens_the_way(story, state):
    state = at_base(story, state)
    state.obstacles["door"].value = 1
    for seed in range(20):
        state.seed = seed
        s, r = resolve(story, state, [ActionStep(action_id="solve:door:2")], "딴다")
        if r.steps[0].roll.grade != "miss":
            assert s.obstacles["door"].fired
            assert "move:top" in candidates(story, s)
            return
    pytest.fail("door never opened")


def test_recommend_three_distinct_and_prefers_tags(story, state):
    buttons = recommend(story, state)
    assert 1 <= len(buttons) <= 3 and len({b.id for b in buttons}) == len(buttons)
    state = at_base(story, state)
    out = []
    dsl.add_tag(state, "edge", "door", out)
    assert recommend(story, state)[0].id.startswith("use_tag:")


def test_talk_free_reveal_and_threat(story, state):
    out = []
    dsl.relation(state, "mira", 2, out)
    s, r = resolve(story, state, [TalkStep(character="mira", topic="topic_key_mira")], "열쇠는요?")
    assert r.steps[0].roll is None
    assert s.graph.edge("knows", "player", "kn_spare_key")
    s, r = resolve(story, state, [TalkStep(character="doha", topic="chat", attitude="threaten")], "말해!")
    assert s.graph.edge("relation", "doha", "player").props["value"] == 0
    assert s.graph.edge("relation", "doha", "player").props["memories"][-1]["kind"] == "threat"


def test_claim_is_recorded_and_lies_can_be_caught(story, state):
    for seed in range(60):
        state.seed = seed
        step = TalkStep(character="mira", claim=True, attitude="deceive", contradicts="kn_spare_key")
        s, r = resolve(story, state, [step], "나는 등대 관리인이 보낸 사람이오")
        claims = s.graph.out("player", "claimed")
        assert claims and claims[0].props["text"].startswith("나는 등대")
        if r.steps[0].roll.grade == "miss":
            assert claims[0].props["exposed"] is True
            assert any(t.trace == "suspicion" for t in s.traces)
            assert s.graph.edge("relation", "mira", "player").props["value"] == -2
            return
    pytest.fail("never exposed in 60 seeds")


def test_trait_counts_once_per_chapter(story, state):
    state = at_base(story, state)
    step = ImproviseStep(target="door", approach="finesse", uses=Uses(trait="trait_quick_hands"))
    s, r = resolve(story, state, [step], "빠른 손으로 딴다")
    assert r.steps[0].roll.modifier == 3
    _, r2 = resolve(story, s, [step], "또 딴다") if s.obstacles["door"].value < 2 else (s, None)
    if r2 is not None:
        assert r2.steps[0].roll.modifier == 2
