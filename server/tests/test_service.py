import json
from pathlib import Path

import pytest
from src.rules.act import Refused
from src.service import Broken, Conflict, GameService
from src.story.load import load_story

STORIES = {"skeleton": load_story(Path(__file__).resolve().parents[2] / "scenarios" / "skeleton")}
STATS = {"do": "stats", "plus2": "skill", "plus1": "charm"}
ASK = {"do": "ask", "text": "어젯밤에 무슨 일 없었습니까?"}
HEARD = {"kind": "topics", "topics": ["밤"]}


def test_a_saved_game_reopens_as_the_same_game(tmp_path):
    service = GameService(STORIES, tmp_path)
    game = service.create("r1", "skeleton")
    service.command(game, "a1", STATS)
    service.command(game, "a2", ASK, HEARD)
    service.command(game, "a3", {"do": "move", "place": "곡물 창고"})
    service.command(game, "a4", {"do": "present", "line": "말 오토.밤.참말", "target": "한스"})
    reopened = GameService(STORIES, tmp_path)
    assert reopened.create("r1", "skeleton") == game
    data, _, state = reopened.load(game)
    assert state == service.load(game)[2] == data["state"]
    assert [t["receipt"] for t in data["turns"]] == ["a1", "a2", "a3", "a4"] and data["turns"][1]["heard"] == HEARD


def test_the_same_receipt_is_processed_once(tmp_path):
    service = GameService(STORIES, tmp_path)
    game = service.create("r1", "skeleton")
    first = service.command(game, "a1", STATS)
    assert service.command(game, "a1", STATS) == first
    with pytest.raises(Conflict):
        service.command(game, "a1", ASK, HEARD)
    with pytest.raises(Refused):
        service.command(game, "a2", {"do": "move", "place": "방앗간"})
    service.command(game, "a2", ASK, HEARD)
    assert [t["receipt"] for t in GameService(STORIES, tmp_path).load(game)[0]["turns"]] == ["a1", "a2"]


@pytest.mark.parametrize("damage", [
    lambda data: data["turns"][0]["changes"][0]["stats"].update({"might": 2}),
    lambda data: data["story"]["머리"].update({"제목": "다른 제목"}),
    lambda data: data["head"].update({"format": 99}),
])
def test_a_broken_save_is_neither_opened_nor_deleted(tmp_path, damage):
    game = GameService(STORIES, tmp_path).create("r1", "skeleton")
    GameService(STORIES, tmp_path).command(game, "a1", STATS)
    path = tmp_path / f"{game}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    damage(data)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(Broken):
        GameService(STORIES, tmp_path).load(game)
    assert json.loads(path.read_text(encoding="utf-8")) == data


def test_a_write_cut_short_leaves_the_old_file(tmp_path, monkeypatch):
    service = GameService(STORIES, tmp_path)
    game = service.create("r1", "skeleton")
    path = tmp_path / f"{game}.json"
    before = path.read_text(encoding="utf-8")
    monkeypatch.setattr("src.save.os.fsync", lambda fd: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(OSError):
        service.command(game, "a1", STATS)
    assert path.read_text(encoding="utf-8") == before and [p.name for p in tmp_path.iterdir()] == [path.name]
