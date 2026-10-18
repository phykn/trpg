from conftest import FakeKev, FakeQwen, noul
from src.models.kev import ModelUnavailable
from src.narrate import Narrator, TagFilter, messages
from src.rules import dsl
from src.rules.resolve import resolve
from src.world.state import ActionStep, ImproviseStep


def test_tag_filter_hides_name_lines():
    f = TagFilter({"t1_1"})
    shown = f.feed("바람이 붑니다.\n@t1_") + f.feed("1 젖은 계단\n@t9_9 남의 것\n끝.")
    f.finish()
    assert shown == "바람이 붑니다.\n끝."
    assert f.names == {"t1_1": "젖은 계단"}


def test_tag_filter_ignores_long_names():
    f = TagFilter({"t1_1"})
    f.feed("@t1_1 " + "가" * 20)
    f.finish()
    assert f.names == {}


def test_messages_carry_facts_changes_and_naming(loaded, state):
    story = loaded.story
    out = []
    dsl.move(state, "player", "base", out)
    state.seed = 2
    new, record = resolve(story, state, [ImproviseStep(purpose="setup", target="door", approach="wits")], "녹을 턴다")
    msgs = messages(story, loaded.style, new, record)
    user = msgs[1]["content"]
    assert msgs[0]["role"] == "system" and "합니다체" in msgs[0]["content"]
    assert "[사실]" in user and "[바뀐 것]" in user and "녹을 턴다" in user
    if any(c.kind == "tag_add" for s in record.steps for c in s.changes):
        assert "[이름 짓기]" in user


async def collect(narrator, loaded, state, record):
    return [e async for e in narrator.narrate(loaded.story, loaded.style, state, record)]


async def test_narration_passes_the_check(loaded, state):
    narrator = Narrator(FakeQwen(["당신은 광장에 있습니다.\n@t1_1 이름"]), FakeKev())
    events = await collect(narrator, loaded, state, state.turns[0])
    assert events[-1] == {"type": "done", "text": "당신은 광장에 있습니다.", "tags": {}}
    assert all("@" not in e.get("text", "") for e in events)


async def test_failed_check_resets_and_rewrites(loaded, state):
    kev = FakeKev({"invents": noul(True)})
    qwen = FakeQwen(["새 상인이 나타납니다.", "광장은 조용합니다."])
    narrator = Narrator(qwen, kev)
    calls = {"n": 0}
    original = kev.decide

    async def decide(text, questions):
        calls["n"] += 1
        if calls["n"] > 1:
            kev.answers = {}
        return await original(text, questions)

    kev.decide = decide
    events = await collect(narrator, loaded, state, state.turns[0])
    kinds = [e["type"] for e in events]
    assert "reset" in kinds and kinds[-1] == "done"
    assert "[고칠 점]" in qwen.calls[1][1]["content"]


async def test_three_failures_end_in_error(loaded, state):
    narrator = Narrator(FakeQwen(["틀림"]), FakeKev({"contradicts": noul(True)}))
    events = await collect(narrator, loaded, state, state.turns[0])
    assert [e["type"] for e in events].count("reset") == 3
    assert events[-1] == {"type": "error", "retry": True}


async def test_low_confidence_complaint_passes(loaded, state):
    narrator = Narrator(FakeQwen(), FakeKev({"contradicts": noul(True, 0.2)}))
    events = await collect(narrator, loaded, state, state.turns[0])
    assert events[-1]["type"] == "done"


async def test_model_error_propagates(loaded, state):
    narrator = Narrator(FakeQwen(error=ModelUnavailable("down")), FakeKev())
    try:
        await collect(narrator, loaded, state, state.turns[0])
    except ModelUnavailable:
        return
    raise AssertionError("expected ModelUnavailable")


def test_opening_turn_uses_the_intro(loaded, state):
    user = messages(loaded.story, loaded.style, state, state.turns[0])[1]["content"]
    assert loaded.story.intro in user and "[플레이어 입력]" not in user
    new, record = resolve(loaded.story, state, [ActionStep(action_id="inspect:mira")], "본다")
    assert "[플레이어 입력]" in messages(loaded.story, loaded.style, new, record)[1]["content"]
