from pathlib import Path

from src.rules.act import act
from src.rules.state import start_state
from src.story.load import load_story
from src.view import make_feed, make_view

DAWN = load_story(Path(__file__).resolve().parents[2] / "scenarios" / "dawn")


def make_state(lines, **fields):
    return {**start_state(DAWN, 0), "notebook": dict.fromkeys(lines, 1), **fields}


def test_what_each_person_said_stays_together_in_the_order_they_first_spoke():
    state = make_state(["말 브람.징수관.거짓말", "말 넬.해 질 녘.참말", "말 브람.독미나리.참말"])
    assert [line["id"] for line in make_view(DAWN, state)[0]["notebook"]["heard"]] == [1, 3, 2]


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
