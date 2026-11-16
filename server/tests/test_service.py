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
    async def read(self, story, state, text, last=None):
        return HEARD


class FakeNarrator:
    def __init__(self, failures=()):
        self.failures = list(failures)

    async def write(self, job):
        if self.failures:
            raise self.failures.pop(0)
        yield {"type": "delta", "text": job["kind"]}
        yield {"type": "result", "text": job["kind"], "checks": []}


def make_service(tmp_path, narrator=None):
    return GameService(STORIES, tmp_path, FakeInterpreter(), narrator)


def send(service, game, receipt, action=None, **body):
    _, story, states = service.load(game)
    if action:
        body["do"] = next(i for i, a in make_view(story, states[-1])[1].items() if a == action)
    return asyncio.run(service.command(game, {"request_id": receipt, "revision": states[-1]["turn"], **body}))


def read_text(service, game, n):
    async def follow():
        return [event async for event in service.stream_text(game, n)]
    return asyncio.run(asyncio.wait_for(follow(), 2))


def test_a_reopened_game_holds_the_same_turns_and_states(tmp_path):
    service = make_service(tmp_path)
    game, _ = service.create("r1", "skeleton")
    send(service, game, "a1", STATS)
    send(service, game, "a2", text=ASK)
    send(service, game, "a3", {"do": "move", "place": "곡물 창고"})
    send(service, game, "a4", {"do": "present", "line": "말 오토.밤.참말", "target": "한스"})
    reopened = make_service(tmp_path)
    assert reopened.create("r1", "skeleton") == (game, service.show(game))
    data, _, states = reopened.load(game)
    assert states == service.load(game)[2] and len(states) == 5 and states[-1] == data["state"]
    assert [t["receipt"] for t in data["turns"]] == ["a1", "a2", "a3", "a4"] and data["turns"][1]["heard"] == HEARD


def test_a_receipt_runs_once_and_a_stale_or_unknown_command_changes_nothing(tmp_path):
    service = make_service(tmp_path)
    game, _ = service.create("r1", "skeleton")
    body = {"request_id": "a1", "revision": 0, "do": "a1"}
    first = asyncio.run(service.command(game, body))
    assert asyncio.run(service.command(game, body)) == first
    with pytest.raises(Conflict):
        send(service, game, "a1", text=ASK)
    with pytest.raises(Conflict):
        asyncio.run(service.command(game, {**body, "request_id": "a2"}))
    assert send(service, game, "a2", do="a999")["kind"] == "refused"
    send(service, game, "a2", text=ASK)
    assert [t["receipt"] for t in make_service(tmp_path).load(game)[0]["turns"]] == ["a1", "a2"]


def test_a_failing_narration_ends_its_stream_and_the_next_ask_writes_it(tmp_path):
    service = make_service(tmp_path, FakeNarrator([KeyError("bug")]))
    game, _ = service.create("r1", "skeleton")
    send(service, game, "a1", STATS)
    read_text(service, game, 1)   # the story's own opening; no model writes it
    send(service, game, "a2", text=ASK)
    assert [e["type"] for e in read_text(service, game, 2)] == ["start", "error"]
    events = read_text(service, game, 2)
    assert events[-1] == {"type": "done"} and not service.texts
    saved = make_service(tmp_path).load(game)[0]["turns"][1]["text"]
    assert [t["text"] for t in saved] == [e["text"] for e in events if e["type"] == "delta"]
    assert read_text(service, game, 2) == read_text(make_service(tmp_path), game, 2)


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


def test_the_narrator_gets_what_it_wrote_before_and_not_what_people_said(tmp_path):
    class Recording(FakeNarrator):
        def __init__(self):
            super().__init__()
            self.jobs = []

        async def write(self, job):
            self.jobs.append(job)
            async for event in super().write(job):
                yield event

    narrator = Recording()
    service = make_service(tmp_path, narrator)
    game, _ = service.create("r1", "skeleton")
    for n, (receipt, action) in enumerate([("a1", STATS), ("a2", {"do": "move", "place": "곡물 창고"})], 1):
        send(service, game, receipt, action)
        read_text(service, game, n)
    # The opening is the story's, so the first scene the model writes already knows it.
    assert [j["kind"] for j in narrator.jobs] == ["scene"]
    assert narrator.jobs[0]["narrated"] == [STORIES["skeleton"].head.opening.scene]
    saved = service.load(game)[0]["turns"][0]["text"]
    assert [t["text"] for t in saved] == [STORIES["skeleton"].head.opening.scene, STORIES["skeleton"].head.opening.first]
