import pytest
from conftest import TEMPLATE, FakeKev, FakeQwen, choice
from src.content.load import load_story
from src.models.kev import ModelUnavailable
from src.service import GameService, Stale
from src.store import SaveStore


@pytest.fixture
def make(tmp_path):
    def build(kev=None, qwen=None):
        loaded = load_story(TEMPLATE)
        return GameService({loaded.story.id: loaded}, SaveStore(tmp_path), kev or FakeKev(), qwen or FakeQwen())
    return build


async def test_catalog_hides_template(make):
    assert make().catalog() == []


async def test_button_turn_saves_and_receipt_replays(make):
    game = make()
    view = await game.start("lighthouse")
    out = await game.act(view.game_id, revision=0, request_id="req_00001", action_id="move:base")
    assert out.kind == "turn" and out.turn == 1 and out.view.place.name == "등대 아래"
    again = await game.act(view.game_id, revision=0, request_id="req_00001", action_id="move:base")
    assert again.turn == 1 and again.view.revision == out.view.revision
    with pytest.raises(Stale):
        await game.act(view.game_id, revision=0, request_id="req_00001", action_id="take:bread")
    with pytest.raises(Stale):
        await game.act(view.game_id, revision=0, request_id="req_00002", action_id="move:square")


async def test_unknown_or_improvise_button_is_refused(make):
    game = make()
    view = await game.start("lighthouse")
    for action in ("move:top", "improvise", "grow:approach:force"):
        with pytest.raises(ValueError):
            await game.act(view.game_id, revision=0, request_id="req_00003", action_id=action)


async def test_text_goes_through_kev_and_rejections_cost_nothing(make):
    kev = FakeKev({"s1": choice("none")})
    game = make(kev=kev)
    view = await game.start("lighthouse")
    out = await game.act(view.game_id, revision=0, request_id="req_00004", text="음...")
    assert out.kind == "rejected" and out.view.revision == 0
    kev.answers = {"s1": choice("take:bread")}
    out = await game.act(view.game_id, revision=0, request_id="req_00005", text="빵을 집는다")
    assert out.kind == "turn" and out.view.player.items[0].name == "갓 구운 빵"


async def test_kev_down_rejects_turn_without_saving(make):
    game = make(kev=FakeKev(error=ModelUnavailable("down")))
    view = await game.start("lighthouse")
    with pytest.raises(ModelUnavailable):
        await game.act(view.game_id, revision=0, request_id="req_00006", text="간다")
    assert (await game.load(view.game_id)).revision == 0


async def test_high_risk_waits_for_confirmation(make):
    game = make()
    view = await game.start("lighthouse")
    await game.act(view.game_id, revision=0, request_id="req_00007", action_id="move:base")
    out = await game.act(view.game_id, revision=1, request_id="req_00008", action_id="solve:door:1")
    assert out.kind == "confirm"
    card = out.view.pending.card
    assert sum(card.odds) == pytest.approx(1) and len(card.costs) == 2
    cancelled = await game.act(view.game_id, revision=2, request_id="req_00009", confirm=card.id, accept=False)
    assert cancelled.view.pending is None and cancelled.view.turn == 1
    out = await game.act(view.game_id, revision=3, request_id="req_00010", action_id="solve:door:1")
    done = await game.act(view.game_id, revision=4, request_id="req_00011", confirm=out.view.pending.card.id)
    assert done.kind == "turn" and done.turn == 2 and done.view.pending is None


async def test_narration_streams_saves_and_caches(make):
    qwen = FakeQwen(["안개가 짙습니다. 당신은 광장에 있습니다."])
    game = make(qwen=qwen)
    view = await game.start("lighthouse")
    events = [e async for e in game.narration(view.game_id, 0)]
    assert events[-1]["type"] == "done"
    assert (await game.load(view.game_id)).journal[0].narration == "안개가 짙습니다. 당신은 광장에 있습니다."
    cached = [e async for e in game.narration(view.game_id, 0)]
    assert cached == [{"type": "done", "text": events[-1]["text"], "tags": {}}]
    assert len(qwen.calls) == 1


async def test_narration_only_for_latest_turn_and_reports_model_errors(make):
    game = make(qwen=FakeQwen(error=ModelUnavailable("down")))
    view = await game.start("lighthouse")
    assert [e async for e in game.narration(view.game_id, 0)] == [{"type": "error", "retry": True}]
    await game.act(view.game_id, revision=0, request_id="req_00012", action_id="move:base")
    assert [e async for e in game.narration(view.game_id, 0)] == [{"type": "error", "retry": False}]


async def test_named_tags_reach_the_view(make):
    game = make(qwen=FakeQwen(["바람이 셉니다.\n@t1_1 젖은 계단"]))
    view = await game.start("lighthouse")
    gid = view.game_id
    await game.act(gid, revision=0, request_id="req_00013", action_id="move:base")
    state = await game.store.load(gid)
    from src.rules import dsl
    out = []
    state.turn = 1
    dsl.add_tag(state, "edge", "door", out)
    state.turns[-1].steps[0].changes += out
    await game.store.save(state)
    events = [e async for e in game.narration(gid, 1)]
    assert events[-1]["tags"] == {"t1_1": "젖은 계단"}
    assert (await game.load(gid)).tags[0].name == "젖은 계단"
