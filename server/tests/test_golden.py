import json

import pytest
from src import service as service_module
from src.fun import measure
from src.onto.save import rebuild
from src.rules.acts import parse
from src.story.validate import NO_ROLL, Run, _creation, _path, _reached, _step
from test_service import STORIES, service

PATHS = [(sid, i) for sid, u in sorted(STORIES.items()) for i in range(len(u.witnesses.get("paths") or []))]


async def replay(svc, monkeypatch, u, i):
    """One witness path through the service, as buttons and card picks with the path's dice."""
    paths = u.witnesses["paths"]
    dice = []
    monkeypatch.setattr(service_module, "roll", lambda seed, t: dice[0])
    out = await svc.create(f"golden-{u.id}-{i}", u.id, {"name": "하루", **_creation(u, paths[i])})
    gid, view = out["game_id"], out["view"]
    for n, st in enumerate(_path(paths, i, "")):
        aid, rolled = _step(st)
        dice[:] = [rolled or NO_ROLL]
        out = await svc.command(gid, {"request_id": f"s{n}", "revision": view["revision"], "action": aid})
        while out["kind"] == "card":
            card = out["view"]["card"]
            ids = [o["id"] for o in card["options"]]
            pick = aid if aid in ids else card["selected"] or ids[0]
            out = await svc.command(gid, {"request_id": f"s{n}c", "revision": out["view"]["revision"],
                                          "card": card["id"], "pick": pick})
        assert out["kind"] == "turn" and out["steps"], (u.id, i, n, aid, out["reason"])
        view = out["view"]
    return gid


@pytest.mark.parametrize(("sid", "i"), PATHS)
async def test_a_witness_path_replays_through_the_service_as_the_validator_ran_it(tmp_path, monkeypatch, sid, i):
    u = STORIES[sid]
    p = u.witnesses["paths"][i]
    gid = await replay(service(tmp_path), monkeypatch, u, i)
    run = Run(u, _creation(u, p))
    for st in _path(u.witnesses["paths"], i, ""):
        aid, rolled = _step(st)
        run.step(parse(aid), rolled or NO_ROLL)
    saved = rebuild(u, json.loads((tmp_path / f"{gid}.json").read_text(encoding="utf-8")))
    (what, target), = p["reach"].items()
    assert _reached(saved.state, what, target)
    assert saved.state == run.s
    assert [e.action for e in saved.log.events] == [e.action for e in run.log.events]


async def test_metrics_on_the_witness_saves(tmp_path, monkeypatch):
    """Each metric read off saves whose every step is known: the fixture for fun.md 4."""
    svc = service(tmp_path)
    for sid, i in PATHS:
        await replay(svc, monkeypatch, STORIES[sid], i)
    m = measure(sorted(tmp_path.glob("*.json")), STORIES, now=0)
    assert m["games"] == len(PATHS) and not m["skipped"]
    assert m["F1"]["sentences"] == 0 and m["F2"]["steps"] == {"button": 109}
    assert m["F3"]["approaches"] == {"door": 2, "drift": 2, "gate_bar": 1, "gorge": 1, "horse": 1, "lamp": 1, "lens": 1}
    assert m["F4"]["rolls"] == 43 and m["F5"]["gaps"] == [2, 3]
    # every lighthouse play past chapter 1 sees the bridge leave on a chapter flag: withdrawn, not driven back
    assert m["F6"] == {"value": None, "answered": 0, "arrived": 0, "pending": 3, "withdrawn": 8}
    assert (m["F7"]["choices"], m["F7"]["read"]) == (5, 4)
    assert m["F8"]["promises_made"] == 0
    assert m["F9"]["snowpass"]["endings"] == {"shared": 2, "whole": 1, "collapse": 1}
    assert m["F9"]["lighthouse"]["endings"] == {"two_lights": 1, "lone_light": 1, "collapse": 1}
    assert m["F10"]["chapters"] == 22 and m["F10"]["deadline"] == 0.0 and m["F11"]["quit"] == 0.0
    assert m["F13"]["rolls"] == 43 and m["F14"]["closed"] == 0
    assert m["F15"]["interpret"]["n"] == 0 and m["F15"]["stuck"] == 0
