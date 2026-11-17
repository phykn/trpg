import json
from pathlib import Path

from fastapi.testclient import TestClient
from src.ai import ModelUnavailable
from src.ai.narrate import Narrator
from src.api import build_app
from src.config import local_settings
from src.game.names import show_name
from src.game.service import GameService
from src.story.load import load_story

DAWN = load_story(Path(__file__).resolve().parents[2] / "scenarios" / "dawn")
ASK = "징수관은 언제 왔습니까?"
HEARD = {ASK: {"kind": "topics", "topics": ["징수관"]}}


class FakeInterpreter:
    def __init__(self, readings):
        self.readings = readings

    async def read(self, story, state, text, last=None):
        return self.readings[text]


class Down:
    async def read(self, story, state, text, last=None):
        raise ModelUnavailable("down")


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
    def __init__(self, passes):
        self.passes = list(passes)

    async def decide(self, state, questions):
        ok = self.passes.pop(0)
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
        return self.send(do=next(a["id"] for a in self.find_line(addr)["acts"]
                                 if a["label"].startswith(f"{person}에게 내민다")))

    def look(self):
        return self.send(do=self.view["place"]["look"]["id"])

    def move(self, place):
        name = show_name(DAWN, "곳", place)
        return self.send(do=next(m["id"] for m in self.view["place"]["moves"] if m["name"] == name))

    def read_text(self, n):
        response = self.client.get(f"/games/{self.game}/turns/{n}/text")
        assert response.status_code == 200 and response.headers["content-type"].startswith("application/x-ndjson")
        return [json.loads(line) for line in response.text.splitlines()]


def test_dawn_is_solved_without_dice_and_no_branch_name_reaches_the_screen(tmp_path):
    player = Player(make_client(tmp_path, FakeInterpreter(HEARD)))
    assert player.view["stage"] == "start"
    player.send(do=next(a["id"] for a in player.view["start"]["acts"] if (a["plus2"], a["plus1"]) == ("wit", "charm")))
    asked = player.send(text=ASK)
    assert asked["said"] == ASK and asked["text"] and asked["feed"][0] == {"kind": "text", "who": "고드릭", "slot": 0, "topics": ["새벽 종", "마을 살림"]}
    assert player.move("숲길")["feed"][0]["kind"] == "move" and not player.view["place"]["looked"]
    assert player.look()["feed"][0] == {"kind": "text", "who": None, "slot": 0} and player.view["place"]["looked"]
    player.present("볼 것 쓸린 자국", "토빈")
    player.move("여관 물레방아")
    player.look()
    player.present("볼 것 여관 나무패", "브람")
    news = [x["id"] for group in player.view["notebook"].values() for x in group if x["new"]]
    assert player.send(read=news)["text"] is False and player.view["badge"] == 0
    who = player.find_line("사람 고드릭")["id"]
    assert who in player.view["conclude"]["who"]
    ending = player.send(conclude={"who": who, "how": player.find_line("볼 것 검푸른 입술")["id"],
                                   "why": player.find_line("볼 것 가방의 쪽지")["id"]})
    # The one named answers first, then the ending (game/07 4절).
    assert [(f["kind"], f["who"]) for f in ending["feed"][:2]] == [("text", "고드릭"), ("ending", None)]
    assert player.view["stage"] == "over"
    assert player.view["ending"]["verdict"] == "solved" and set(player.view["ending"]["answers"].values()) == {"hit"}
    assert player.call("get", f"/games/{player.game}") == player.view
    assert len(player.call("get", f"/games/{player.game}/turns?from=1")) == player.view["revision"]
    seen = json.dumps(player.replies, ensure_ascii=False)
    assert not [word for word in ("거짓말", "깨진 뒤", "풀린 뒤", "참말") if word in seen]


def test_errors_keep_the_game_as_it_was(tmp_path):
    client = make_client(tmp_path, Down())
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


def test_text_shows_only_once_checked_and_is_retried_after_an_error(tmp_path):
    answer = "징수관이 숨졌소. 새벽 종이 울리기 전에 결백을 밝혀야 하오. 해 지기 전에 장부만 걷고 떠났소."
    llm = FakeLLM([ModelUnavailable("down"), "장부만 걷고 갔소. 새벽 종 얘기라면 내가 알지.", answer])
    player = Player(make_client(tmp_path, FakeInterpreter(HEARD), Narrator(llm, FakeChecks([False, True]))))
    player.send(do=player.view["start"]["acts"][0]["id"])
    # The first turn is the story's opening, there at once.
    assert player.read_text(1) == [{"type": "start", "slot": 0}, {"type": "delta", "slot": 0, "text": DAWN.head.opening.scene},
                                   {"type": "end", "slot": 0}, {"type": "start", "slot": 1},
                                   {"type": "delta", "slot": 1, "text": DAWN.head.opening.first}, {"type": "end", "slot": 1},
                                   {"type": "done"}]
    player.send(text=ASK)
    assert [e["type"] for e in player.read_text(2)] == ["start", "error"]
    events = player.read_text(2)
    # Only the text that passed reaches the screen: the failed first draft is never shown.
    assert events == player.read_text(2) == [{"type": "start", "slot": 0},
                                   {"type": "delta", "slot": 0, "text": f"{answer} "},
                                   {"type": "end", "slot": 0}, {"type": "done"}]
    saved = json.loads((tmp_path / f"{player.game}.json").read_text(encoding="utf-8"))["turns"][1]["text"]
    assert [c["failed"] for c in saved[0]["checks"]] == [["added", "meaning", "case"], []]
    assert player.client.get(f"/games/{player.game}/turns/9/text").status_code == 404


def test_text_can_be_polled_for_a_tunnel_that_holds_streams_back(tmp_path):
    llm = FakeLLM(["장부만 걷고 갔소. 새벽 종 얘기라면 내가 알지.", "해 지기 전에 장부만 걷고 떠났소. 새벽 종 얘기라면 내가 알지."])
    player = Player(make_client(tmp_path, FakeInterpreter(HEARD), Narrator(llm, FakeChecks([False, True]))))
    player.send(do=player.view["start"]["acts"][0]["id"])
    player.send(text=ASK)
    events, after = [], 0
    while not events or events[-1]["type"] not in ("done", "error"):
        polled = player.client.get(f"/games/{player.game}/turns/2/text/poll", params={"after": after}).json()
        events, after = events + polled["events"], polled["next"]
    assert [e["type"] for e in events] == ["start", "delta", "end", "done"]
    # Once saved, every poll gets the whole text again, so a screen that saw part of it still ends whole.
    again = player.client.get(f"/games/{player.game}/turns/2/text/poll", params={"after": 3}).json()
    assert again["events"] == player.read_text(2) and again["next"] == len(again["events"])
    assert player.client.get(f"/games/{player.game}/turns/9/text/poll").status_code == 404


def test_health_answers_without_auth():
    response = TestClient(build_app(local_settings(), None)).get("/health")
    assert response.status_code == 200 and response.json() == {"ok": True}
