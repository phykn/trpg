import json
from pathlib import Path

from fastapi.testclient import TestClient
from run_api import build_app, local_settings
from src.models import ModelUnavailable
from src.narrate import Narrator
from src.service import GameService
from src.story.load import load_story
from src.view import show_name

SCENARIOS = Path(__file__).resolve().parents[2] / "scenarios"
DAWN = load_story(SCENARIOS / "dawn")
BRANCHES = ("거짓말", "깨진 뒤", "풀린 뒤", "참말")


class FakeInterpreter:
    def __init__(self, readings):
        self.readings = readings

    async def read(self, story, state, text):
        return self.readings[text]


class FakeLLM:
    def __init__(self, texts):
        self.texts = list(texts)

    async def stream(self, messages, max_tokens):
        text = self.texts.pop(0)
        if isinstance(text, Exception):
            raise text
        for word in text.split(" "):
            yield word + " "


class FakeChecks:
    def __init__(self, verdicts):
        self.verdicts = list(verdicts)

    async def decide(self, state, questions):
        ok = self.verdicts.pop(0)
        return {key: {"noul": float(ok != (key == "added"))} for key in questions}


def make_client(tmp_path, interpreter, narrator=None):
    client = TestClient(build_app(local_settings(), GameService({"dawn": DAWN}, tmp_path, interpreter, narrator)))
    client.auth = ("local", "local")
    return client


class Player:
    def __init__(self, client):
        self.client = client
        self.replies = []
        reply = self.call("post", "/games", {"request_id": "g1", "story": "dawn"})
        self.game, self.view = reply["game"], reply["view"]

    def call(self, method, path, body=None):
        response = self.client.request(method, path, json=body)
        assert response.status_code == 200, response.text
        self.replies.append(response.json())
        return response.json()

    def send(self, **body):
        body = {"request_id": f"r{len(self.replies)}", "revision": self.view["revision"], **body}
        reply = self.call("post", f"/games/{self.game}/commands", body)
        assert reply["kind"] == "turn" and not any(f["kind"] == "roll" for f in reply["feed"])
        self.view = reply["view"]
        return reply

    def find_line(self, addr):
        line = DAWN.lines[addr]
        text = show_name(DAWN, line.kind, line.name) if line.kind != "볼 것" or DAWN.things[line.name].item else line.text
        return next(x for group in self.view["notebook"].values() for x in group if x["text"] == text)

    def present(self, addr, person):
        label = f"{person}에게 내민다"
        return self.send(do=next(a["id"] for a in self.find_line(addr)["acts"] if a["label"].startswith(label)))

    def move(self, place):
        name = show_name(DAWN, "곳", place)
        return self.send(do=next(m["id"] for m in self.view["place"]["moves"] if m["name"] == name))


def test_dawn_is_solved_without_dice_and_no_branch_name_reaches_the_screen(tmp_path):
    text = "징수관은 언제 왔습니까?"
    player = Player(make_client(tmp_path, FakeInterpreter({text: {"kind": "topics", "topics": ["징수관"]}})))
    assert player.view["stage"] == "start"
    player.send(do=next(a["id"] for a in player.view["start"]["acts"] if (a["plus2"], a["plus1"]) == ("wit", "charm")))
    asked = player.send(text=text)
    assert asked["said"] == text and asked["text"] and asked["feed"][0] == {"kind": "text", "who": "고드릭", "slot": 0}
    assert player.move("숲길")["feed"][0]["kind"] == "move"
    player.present("볼 것 쓸린 자국", "토빈")
    player.move("여관 물레방아")
    player.present("볼 것 여관 나무패", "브람")
    news = [x["id"] for group in player.view["notebook"].values() for x in group if x["new"]]
    assert player.send(read=news)["text"] is False and player.view["badge"] == 0
    who = player.find_line("사람 고드릭")["id"]
    assert who in player.view["conclude"]["who"]
    ending = player.send(conclude={"who": who, "how": player.find_line("볼 것 검푸른 입술")["id"],
                                   "why": player.find_line("볼 것 가방의 쪽지")["id"]})
    assert ending["feed"][0]["kind"] == "ending" and player.view["stage"] == "over"
    assert player.view["ending"]["verdict"] == "solved" and set(player.view["ending"]["answers"].values()) == {"hit"}
    assert player.call("get", f"/games/{player.game}") == player.view
    assert len(player.call("get", f"/games/{player.game}/turns?from=1")) == player.view["revision"]
    seen = json.dumps(player.replies, ensure_ascii=False)
    assert not [word for word in BRANCHES if word in seen]


def test_errors_keep_the_game_as_it_was(tmp_path):
    client = make_client(tmp_path, None)
    assert client.get("/stories", auth=("local", "wrong")).status_code == 401
    assert client.get("/games/0123456789abcdef").status_code == 404
    reply = client.post("/games", json={"request_id": "g1", "story": "dawn"}).json()
    game, view = reply["game"], reply["view"]
    stats = {"request_id": "r1", "revision": 0, "do": view["start"]["acts"][0]["id"]}
    assert client.post(f"/games/{game}/commands", json={**stats, "text": "x", "read": [1]}).status_code == 422
    refused = client.post(f"/games/{game}/commands", json={**stats, "do": "a999"}).json()
    assert refused["kind"] == "refused" and refused["code"] == "unknown_act" and refused["view"] == view
    first = client.post(f"/games/{game}/commands", json=stats).json()
    assert client.post(f"/games/{game}/commands", json=stats).json() == first
    stale = client.post(f"/games/{game}/commands", json={**stats, "request_id": "r2"})
    assert stale.status_code == 409 and stale.json()["view"] == first["view"]
    asked = client.post(f"/games/{game}/commands", json={"request_id": "r3", "revision": 1, "text": "안녕하십니까"})
    assert asked.status_code == 503 and client.get(f"/games/{game}").json() == first["view"]


def test_text_is_written_once_rewritten_when_it_fails_and_retried_after_an_error(tmp_path):
    text = "징수관은 언제 왔습니까?"
    llm = FakeLLM([ModelUnavailable("down"), "사당에 들어섭니다.", "장부만 걷고 갔소.", "해 지기 전에 떠났소."])
    narrator = Narrator(llm, FakeChecks([True, False, True]))
    player = Player(make_client(tmp_path, FakeInterpreter({text: {"kind": "topics", "topics": ["징수관"]}}), narrator))
    player.send(do=player.view["start"]["acts"][0]["id"])

    def read(n):
        response = player.client.get(f"/games/{player.game}/turns/{n}/text")
        assert response.status_code == 200 and response.headers["content-type"].startswith("application/x-ndjson")
        return [json.loads(line) for line in response.text.splitlines()]

    assert [e["type"] for e in read(1)] == ["start", "error"]
    assert [e["type"] for e in read(1)] == ["start", "delta", "delta", "end", "done"]
    player.send(text=text)
    events = read(2)
    assert [e["type"] for e in events] == ["start", "delta", "delta", "delta", "replace", "end", "done"]
    assert events[4] == {"type": "replace", "slot": 0, "text": "해 지기 전에 떠났소. "}
    assert read(2) == [{"type": "start", "slot": 0}, {"type": "delta", "slot": 0, "text": "해 지기 전에 떠났소. "},
                       {"type": "end", "slot": 0}, {"type": "done"}]
    saved = json.loads((tmp_path / f"{player.game}.json").read_text(encoding="utf-8"))["turns"][1]["text"]
    assert [c["failed"] for c in saved[0]["checks"]] == [["added", "meaning"], []]
    assert player.client.get(f"/games/{player.game}/turns/9/text").status_code == 404
