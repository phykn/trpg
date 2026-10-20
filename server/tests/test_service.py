import json

import httpx
import pytest
from conftest import REPO
from run_api import build_app
from src.service import Conflict, GameService, Incompatible, Missing
from src.story.validate import load_all

STORIES = load_all(REPO / "scenarios")
CREATION = {"approaches": {"force": 1, "finesse": 2, "wits": 1, "charm": 0}, "traits": ["sailor", "tinker"]}


class FakeInterpreter:

    def __init__(self, plans):
        self.plans = plans

    async def plan(self, u, g, text):
        return {"plan": [{"action": a} for a in self.plans[text]]}

    async def fill(self, u, g, st):
        return st

    async def relevant(self, u, o, p, a, values, text):
        return values


def service(tmp_path, plans=None):
    return GameService(STORIES, tmp_path, FakeInterpreter(plans) if plans else None, seeds=lambda: 7)


@pytest.fixture
def svc(tmp_path):
    return service(tmp_path)


async def new(svc, rid="r-new"):
    out = await svc.create(rid, "lighthouse", CREATION)
    return out["game_id"], out["view"]


async def cmd(svc, gid, view, rid, **body):
    return await svc.command(gid, {"request_id": rid, "revision": view["revision"], **body})


async def leave(svc, gid, out, rid):
    """A sentence that goes somewhere stops at the move card; take the way it chose."""
    card = out["view"]["card"]
    assert card["kind"] == "move" and not out["steps"]
    return await cmd(svc, gid, out["view"], rid, card=card["id"], pick=card["selected"])


async def press(svc, gid, view, action, rid):
    out = await cmd(svc, gid, view, rid, action=action)
    return out, out["view"]


async def test_create_is_idempotent_by_request_id(svc):
    gid, view = await new(svc)
    again, _ = await new(svc)
    assert again == gid
    with pytest.raises(Conflict):
        await svc.create("r-new", "lighthouse", {**CREATION, "traits": ["sailor", "islander"]})
    assert view["revision"] == 0 and view["chapter"]["title"] == "등대에 오르다"
    assert view["scene"]["place"]["name"] == "선착장" and view["ending"] is None


async def test_button_runs_one_step_and_same_request_gives_same_response(svc):
    gid, view = await new(svc)
    out = await cmd(svc, gid, view, "r1", action="go:village")
    assert out["kind"] == "turn" and out["turn"] == 1 and out["steps"][0]["result"] == "none"
    assert out["view"]["revision"] == 1 and out["view"]["scene"]["place"]["id"] == "village"
    again = await cmd(svc, gid, view, "r1", action="go:village")
    assert again == out
    with pytest.raises(Conflict) as e:
        await cmd(svc, gid, view, "r1", action="go:yard")
    assert e.value.view["revision"] == 1


async def test_stale_revision_is_a_conflict_with_the_view(svc):
    gid, view = await new(svc)
    await cmd(svc, gid, view, "r1", action="go:village")
    with pytest.raises(Conflict) as e:
        await cmd(svc, gid, view, "r2", action="go:dock")
    assert e.value.view["revision"] == 1


async def test_out_of_candidate_action_is_refused(svc):
    gid, view = await new(svc)
    out = await cmd(svc, gid, view, "r1", action="go:lamp_room")
    assert out["kind"] == "refused" and out["reason"] and out["view"]["revision"] == 0


async def test_roll_card_preview_is_the_step(svc):
    gid, view = await new(svc)
    _, view = await press(svc, gid, view, "go:village", "r1")
    _, view = await press(svc, gid, view, "go:yard", "r2")
    out = await cmd(svc, gid, view, "r3", action="try:door:finesse")
    assert out["kind"] == "card" and not out["steps"]
    card = out["view"]["card"]
    assert card["kind"] == "roll" and card["selected"] == "try:door:finesse"
    ids = [o["id"] for o in card["options"]]
    assert ids[-1] == "try:door:finesse" and "try:door:finesse;rely=trait:tinker" in ids
    pick = next(o for o in card["options"] if o["id"] == "try:door:finesse;rely=trait:tinker")
    assert [m["value"] for m in pick["preview"]["mods"]] == [2, 1, -1]
    assert pick["note"] == "1번 남음" and pick["preview"]["risk"] == "normal"
    bad = await cmd(svc, gid, out["view"], "r4", card=card["id"], pick="try:door:force")
    assert bad["kind"] == "refused"
    done = await cmd(svc, gid, out["view"], "r5", card=card["id"], pick=pick["id"])
    step = done["steps"][0]
    assert step["mods"] == pick["preview"]["mods"] and step["risk"] == pick["preview"]["risk"]
    assert step["total"] == step["roll"]["d1"] + step["roll"]["d2"] + 2
    assert done["view"]["card"] is None


async def test_card_cancel_and_stale_card(svc):
    gid, view = await new(svc)
    _, view = await press(svc, gid, view, "go:yard", "r1")
    out = await cmd(svc, gid, view, "r2", action="try:bridge:force")
    card = out["view"]["card"]
    gone = await cmd(svc, gid, out["view"], "r3", card=card["id"], cancel=True)
    assert gone["view"]["card"] is None and gone["view"]["revision"] == out["view"]["revision"] + 1
    late = await cmd(svc, gid, gone["view"], "r4", card=card["id"], pick=card["options"][-1]["id"])
    assert late["kind"] == "refused"


async def test_chain_stops_for_a_roll_card_after_its_first_step(tmp_path):
    svc = service(tmp_path, {"문으로": ["go:yard", "try:door:force"]})
    gid, view = await new(svc)
    _, view = await press(svc, gid, view, "go:village", "r1")
    out = await leave(svc, gid, await cmd(svc, gid, view, "r2", text="문으로"), "r3")
    assert out["kind"] == "card" and [s["action"] for s in out["steps"]] == ["go:yard"]
    card = out["view"]["card"]
    assert card["kind"] == "roll" and card["options"][-1]["preview"]["risk"] == "high"


async def test_a_roll_card_from_a_sentence_keeps_the_sentence_for_the_narrator(tmp_path):
    svc = service(tmp_path, {"문을 비집어 연다": ["try:door:finesse"]})
    gid, view = await new(svc)
    for i, a in enumerate(["go:village", "go:yard"]):
        _, view = await press(svc, gid, view, a, f"r{i}")
    out = await cmd(svc, gid, view, "t1", text="문을 비집어 연다")
    card = out["view"]["card"]
    await cmd(svc, gid, out["view"], "t2", card=card["id"], pick=card["selected"])
    _, g = await svc.load(gid)
    assert g.presentation["turns"][-1]["text"] == "문을 비집어 연다"


async def test_a_high_step_waits_for_a_confirm_card(tmp_path):
    svc = service(tmp_path, {"올라가 고른다": ["go:lamp_room", "choose:g_oil:beacon"]})
    gid, view = await new(svc)
    for i, a in enumerate(["go:village", "go:yard"]):
        _, view = await press(svc, gid, view, a, f"r{i}")
    for i in range(8):
        out = await cmd(svc, gid, view, f"t{i}", action="try:door:finesse")
        card = out["view"]["card"]
        res = await cmd(svc, gid, out["view"], f"p{i}", card=card["id"], pick="try:door:finesse")
        view = res["view"]
        if (ob := view["scene"]["obstacles"][0])["fill"] == ob["boxes"]:
            break
    out = await leave(svc, gid, await cmd(svc, gid, view, "c1", text="올라가 고른다"), "c1.go")
    assert [s["action"] for s in out["steps"]] == ["go:lamp_room"]
    assert any(c["kind"] == "chapter" for c in out["steps"][0]["changes"])
    card = out["view"]["card"]
    assert card["kind"] == "confirm" and card["options"][0]["id"] == "choose:g_oil:beacon"
    assert out["view"]["chapter"]["k"] == 2 and out["view"]["growth"]
    growth = out["view"]["growth"]
    assert {g["kind"] for g in growth} == {"approach", "trait"}
    swap = next(g for g in growth if g["kind"] == "trait")
    assert swap["label"].endswith(swap["name"]) and "→" in swap["name"] and ":" not in swap["name"]
    done = await cmd(svc, gid, out["view"], "c2", card=card["id"], pick="choose:g_oil:beacon")
    assert done["steps"][0]["action"] == "choose:g_oil:beacon"
    assert done["view"]["journal"]["choices"][-1]["kind"] == "fork"


async def test_restart_gives_the_same_view(svc, tmp_path):
    gid, view = await new(svc)
    _, view = await press(svc, gid, view, "go:village", "r1")
    _, view = await press(svc, gid, view, "go:yard", "r2")
    out = await cmd(svc, gid, view, "r3", action="try:door:finesse")
    again = service(tmp_path)
    assert await again.view(gid) == out["view"]
    replay = await cmd(again, gid, view, "r3", action="try:door:finesse")
    assert replay == out


async def test_missing_and_incompatible_saves(svc, tmp_path):
    with pytest.raises(Missing):
        await svc.view("g_" + "0" * 32)
    with pytest.raises(Missing):
        await svc.view("../etc")
    gid, _ = await new(svc)
    path = tmp_path / f"{gid}.json"
    data = json.loads(path.read_text())
    path.write_text(json.dumps({**data, "schema_version": 1}))
    with pytest.raises(Incompatible):
        await service(tmp_path).view(gid)


async def test_text_without_an_interpreter_is_refused(svc):
    gid, view = await new(svc)
    out = await cmd(svc, gid, view, "r1", text="마을로 간다")
    assert out["kind"] == "refused" and out["view"]["revision"] == 0


@pytest.fixture
def client(svc):
    app = build_app(service=svc, basic_auth_user="u", basic_auth_pass="p", cors_origins=[])
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t", auth=("u", "p"))


async def test_http_routes(client):
    async with client:
        assert (await client.get("/stories", auth=("u", "x"))).status_code == 401
        stories = (await client.get("/stories")).json()
        assert stories[0]["id"] == "lighthouse" and stories[0]["pick"] == 2
        r = await client.post("/games", json={"request_id": "abc", "story": "lighthouse", "creation": CREATION})
        assert r.status_code == 422
        r = await client.post("/games", json={"request_id": "abc", "story": "lighthouse",
                                              "creation": {**CREATION, "name": " 해원 "}})
        gid, view = r.json()["game_id"], r.json()["view"]
        assert view["player"]["name"] == "해원"
        assert (await client.get(f"/games/{gid}")).json() == view
        body = {"request_id": "c1", "revision": 0, "action": "go:village"}
        r = await client.post(f"/games/{gid}/commands", json=body)
        assert r.status_code == 200 and r.json()["kind"] == "turn"
        r = await client.post(f"/games/{gid}/commands", json={**body, "request_id": "c2"})
        assert r.status_code == 409 and r.json()["view"]["revision"] == 1
        r = await client.post(f"/games/{gid}/commands", json={"request_id": "c3", "revision": 1})
        assert r.status_code == 422
        r = await client.post(f"/games/{gid}/commands", json={"request_id": "c3", "revision": 1, "card": "c1"})
        assert r.status_code == 422
        assert (await client.get("/games/g_" + "1" * 32)).status_code == 404
        r = await client.post("/games", json={"request_id": "x", "story": "nope", "creation": {**CREATION, "name": "a"}})
        assert r.status_code == 422


async def test_a_sentence_move_waits_on_a_move_card_naming_who_comes(tmp_path):
    plans = {"같이 가자": ["talk:yunseul:come"], "마을": ["go:village"]}
    svc = GameService(STORIES, tmp_path, FakeInterpreter(plans), seeds=lambda: 3)
    gid, view = await new(svc)
    out = await cmd(svc, gid, view, "r1", text="같이 가자")
    card = out["view"]["card"]
    out = await cmd(svc, gid, out["view"], "r2", card=card["id"], pick=card["selected"])
    assert out["steps"][0]["result"] == "success"     # seed 3 wins the charm roll
    assert [p["with"] for p in out["view"]["scene"]["people"]] == [True]
    out = await cmd(svc, gid, out["view"], "r3", text="마을")
    card = out["view"]["card"]
    assert card["kind"] == "move" and not out["steps"] and card["selected"] == "go:village"
    assert card["options"][0] == {"id": "go:village", "label": "바닷가 마을", "effects": ["윤슬과 함께"]}
    out = await cmd(svc, gid, out["view"], "r4", card=card["id"], pick="go:village")
    assert out["view"]["scene"]["place"]["id"] == "village"
    assert [p["id"] for p in out["view"]["scene"]["people"] if p["with"]] == ["yunseul"]


async def test_a_move_card_can_take_another_way_or_be_closed(tmp_path):
    svc = service(tmp_path, {"위로": ["go:yard"]})
    gid, view = await new(svc)
    _, view = await press(svc, gid, view, "go:village", "r1")
    out = await cmd(svc, gid, view, "r2", text="위로")
    card = out["view"]["card"]
    assert [o["id"] for o in card["options"]][:1] == ["go:yard"] and "go:dock" in card["options"][1]["id"]
    closed = await cmd(svc, gid, out["view"], "r3", card=card["id"], cancel=True)
    assert closed["view"]["card"] is None and closed["view"]["scene"]["place"]["id"] == "village"
    out = await cmd(svc, gid, closed["view"], "r4", text="위로")
    card = out["view"]["card"]
    out = await cmd(svc, gid, out["view"], "r5", card=card["id"], pick="go:dock")
    assert [s["action"] for s in out["steps"]] == ["go:dock"]


async def test_a_button_move_needs_no_card(svc):
    gid, view = await new(svc)
    out, view = await press(svc, gid, view, "go:village", "r1")
    assert out["kind"] == "turn" and view["card"] is None and view["scene"]["place"]["id"] == "village"
