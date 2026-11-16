from pathlib import Path

from src.rules.act import act
from src.rules.state import start_state
from src.story.load import load_story
from src.view import make_feed, make_view
from tests.test_act import LOCK, LOOK, STATS, ask, doing, go
from tests.test_act import STORY as SKELETON
from tests.test_act import play as play_skeleton

DAWN = load_story(Path(__file__).resolve().parents[2] / "scenarios" / "dawn")


def make_state(lines, **fields):
    return {**start_state(DAWN, 0), "notebook": dict.fromkeys(lines, 1), **fields}


def test_what_each_person_said_stays_together_in_the_order_they_first_spoke():
    state = make_state(["말 브람.징수관.거짓말", "말 넬.해 질 녘.참말", "말 브람.독미나리.참말"])
    assert [line["id"] for line in make_view(DAWN, state)[0]["notebook"]["heard"]] == [1, 3, 2]


def test_a_person_shows_their_intro_and_what_they_said_and_an_item_its_intro():
    state = make_state(["사람 브람", "말 브람.징수관.거짓말", "말 넬.해 질 녘.참말", "볼 것 쇠꼬챙이", "볼 것 목 자국"])
    book = make_view(DAWN, state)[0]["notebook"]
    assert [(x["intro"], x["about"]) for x in book["people"]] == [(DAWN.people["브람"].intro, [2])]
    assert [x["intro"] for x in book["items"] + book["seen"]] == [DAWN.things["쇠꼬챙이"].intro, None]


def test_a_visited_place_shows_its_look_and_what_was_seen_there_and_a_clue_where_and_whom_it_tells_of():
    lines = ["곳 숲길", "곳 여관 물레방아", "볼 것 여관 나무패", "볼 것 목 자국", "사람 넬", "말 넬.해 질 녘.참말"]
    book = make_view(DAWN, make_state(lines, visited=["숲길"]))[0]["notebook"]
    assert [(x["intro"], x["about"]) for x in book["places"]] == [(DAWN.places["숲길"].desc, [3, 4]), (None, [])]
    assert [x["about"] for x in book["seen"]] == [[1, 2], [1]]
    assert book["heard"][0]["about"] == [5, 2]


def test_the_badge_counts_every_unread_line():
    state = make_state(["곳 숲길", "말 넬.해 질 녘.참말", "볼 것 목 자국"], read=["곳 숲길"])
    assert make_view(DAWN, state)[0]["badge"] == 2


def test_the_first_turn_tells_the_lines_written_before_it():
    action = {"do": "stats", "plus2": "wit", "plus1": "charm"}
    result = act(DAWN, start_state(DAWN, 0), action, None)
    book = result["state"]["notebook"]
    opening = [a for a, turn in book.items() if turn == 0]
    ids = {a: i for i, a in enumerate(book, 1)}
    notes = [f for f in make_feed(DAWN, {"action": action, **result}, ids, opening) if f["kind"] == "note"]
    assert opening and notes[0]["lines"] == [ids[a] for a in opening]


def test_the_ending_lists_what_was_met_before_what_never_was():
    state = make_state(["말 브람.징수관.거짓말"], stats={}, conclusion={"who": None, "how": None, "why": None},
                       withheld=["꺼림 토빈.숲길에서 본 것"])
    missed = make_view(DAWN, state)[0]["ending"]["missed"]
    assert missed["lies"][0].startswith("브람") and "듣지 못함" not in missed["lies"][0]
    assert all(text.endswith("· 듣지 못함") for text in missed["lies"][1:])
    assert missed["held"][0] == "토빈 — 숲길에서 본 것" and missed["held"][1].endswith("· 꺼내지 못함")



def test_a_typed_action_offers_the_dice_it_could_bet_and_nothing_else_does():
    state, rs = play_skeleton(0, [STATS, ask("밤"), doing("press")])
    assert [o["label"].split(" · ")[0] for o in make_view(SKELETON, state, rs[-1])[0]["offers"]] == ["오토를 몰아세운다"]
    assert make_view(SKELETON, state)[0]["offers"] == []
    state, rs = play_skeleton(0, [STATS, go("곡물 창고"), LOOK, doing("sneak", LOCK)])
    assert [o["label"].split(" · ")[0] for o in make_view(SKELETON, state, rs[-1])[0]["offers"]] == ["몰래 연다"]


def test_a_guessed_action_offers_its_dice_but_the_answer_and_impressions_are_the_readings():
    guess = {"do": "ask", "text": "x"}, {"kind": "chat", "guess": {"method": "press", "target": None}}
    state, rs = play_skeleton(0, [STATS, ask("밤"), guess])
    assert [o["label"].split(" · ")[0] for o in make_view(SKELETON, state, rs[-1])[0]["offers"]] == ["오토를 몰아세운다"]
    assert state["impressions"]["오토"] == {} and rs[-1]["talk"][0] == {"chat": "오토"}
