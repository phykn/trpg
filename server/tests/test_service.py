import asyncio
import json
from pathlib import Path

import pytest
from src.service import Broken, Conflict, GameService
from src.story.load import load_story
from src.view import make_view

STORIES = {"skeleton": load_story(Path(__file__).resolve().parents[2] / "scenarios" / "skeleton")}
STATS = {"do": "stats", "plus2": "skill", "plus1": "charm"}
ASK = "어젯밤에 무슨 일 없었습니까?"
HEARD = {"kind": "topics", "topics": ["밤"]}


class FakeInterpreter:
    async def read(self, story, state, text):
        return HEARD


def make_service(tmp_path):
    return GameService(STORIES, tmp_path, FakeInterpreter(), None)


def send(service, game, receipt, action=None, **body):
    _, story, state = service.load(game)
    if action:
        body["do"] = next(i for i, a in make_view(story, state)[1].items() if a == action)
    return asyncio.run(service.command(game, {"request_id": receipt, "revision": state["turn"], **body}))


def test_a_saved_game_reopens_as_the_same_game(tmp_path):
    service = make_service(tmp_path)
    game, _ = service.create("r1", "skeleton")
    send(service, game, "a1", STATS)
    send(service, game, "a2", text=ASK)
    send(service, game, "a3", {"do": "move", "place": "곡물 창고"})
    send(service, game, "a4", {"do": "present", "line": "말 오토.밤.참말", "target": "한스"})
    reopened = make_service(tmp_path)
    assert reopened.create("r1", "skeleton") == (game, service.show(game))
    data, _, state = reopened.load(game)
    assert state == service.load(game)[2] == data["state"]
    assert [t["receipt"] for t in data["turns"]] == ["a1", "a2", "a3", "a4"] and data["turns"][1]["heard"] == HEARD


def test_the_same_receipt_is_processed_once(tmp_path):
    service = make_service(tmp_path)
    game, _ = service.create("r1", "skeleton")
    first = asyncio.run(service.command(game, {"request_id": "a1", "revision": 0, "do": "a1"}))
    assert asyncio.run(service.command(game, {"request_id": "a1", "revision": 0, "do": "a1"})) == first
    with pytest.raises(Conflict):
        send(service, game, "a1", text=ASK)
    assert send(service, game, "a2", do="a999")["kind"] == "refused"
    send(service, game, "a2", text=ASK)
    assert [t["receipt"] for t in make_service(tmp_path).load(game)[0]["turns"]] == ["a1", "a2"]


@pytest.mark.parametrize(("damage", "reason"), [
    (lambda data: data["turns"][0]["changes"][0]["stats"].update({"might": 2}), "broken"),
    (lambda data: data["story"]["머리"].update({"제목": "다른 제목"}), "broken"),
    (lambda data: data["head"].update({"format": 99}), "incompatible"),
])
def test_a_broken_save_is_neither_opened_nor_deleted(tmp_path, damage, reason):
    game, _ = make_service(tmp_path).create("r1", "skeleton")
    send(make_service(tmp_path), game, "a1", STATS)
    path = tmp_path / f"{game}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    damage(data)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(Broken, match=reason):
        make_service(tmp_path).load(game)
    assert json.loads(path.read_text(encoding="utf-8")) == data


def test_a_write_cut_short_leaves_the_old_file(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    game, _ = service.create("r1", "skeleton")
    path = tmp_path / f"{game}.json"
    before = path.read_text(encoding="utf-8")
    monkeypatch.setattr("src.save.os.fsync", lambda fd: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(OSError):
        send(service, game, "a1", STATS)
    assert path.read_text(encoding="utf-8") == before and [p.name for p in tmp_path.iterdir()] == [path.name]
