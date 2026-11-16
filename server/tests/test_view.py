from pathlib import Path

from src.rules.act import act
from src.rules.state import start_state
from src.story.load import load_story
from src.view import make_feed, make_view

DAWN = load_story(Path(__file__).resolve().parents[2] / "scenarios" / "dawn")


def test_heard_lines_are_grouped_by_speaker_in_order_of_first_appearance():
    lines = ["말 브람.징수관.거짓말", "말 넬.해 질 녘.참말", "말 브람.독미나리.참말"]
    state = {**start_state(DAWN, 0), "notebook": dict.fromkeys(lines, 1)}
    heard = make_view(DAWN, state)[0]["notebook"]["heard"]
    assert [line["id"] for line in heard] == [1, 3, 2]


def test_the_first_turn_tells_what_was_written_before_it():
    action = {"do": "stats", "plus2": "wit", "plus1": "charm"}
    result = act(DAWN, start_state(DAWN, 0), action, None)
    opening = [a for a, t in result["state"]["notebook"].items() if t == 0]
    ids = {a: i for i, a in enumerate(result["state"]["notebook"], 1)}
    notes = [f for f in make_feed(DAWN, {"action": action, **result}, ids, opening) if f["kind"] == "note"]
    assert opening and notes[0]["lines"] == [ids[a] for a in opening]


def test_the_badge_counts_every_unread_line():
    lines = ["곳 숲길", "말 넬.해 질 녘.참말", "볼 것 목 자국"]
    state = {**start_state(DAWN, 0), "notebook": dict.fromkeys(lines, 1), "read": ["곳 숲길"]}
    assert make_view(DAWN, state)[0]["badge"] == 2


def test_the_ending_marks_what_was_never_met():
    blank = {"who": None, "how": None, "why": None}
    state = {**start_state(DAWN, 0), "stats": {}, "conclusion": blank,
             "notebook": dict.fromkeys(["말 브람.징수관.거짓말"], 1), "withheld": ["꺼림 토빈.숲길에서 본 것"]}
    missed = make_view(DAWN, state)[0]["ending"]["missed"]
    assert missed["lies"][0].startswith("브람") and "듣지 못함" not in missed["lies"][0]
    assert all(t.endswith("· 듣지 못함") for t in missed["lies"][1:])
    assert missed["held"][0] == "토빈 — 숲길에서 본 것" and missed["held"][1].endswith("· 꺼내지 못함")
