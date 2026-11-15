from pathlib import Path

from src.rules.state import start_state
from src.story.load import load_story
from src.view import make_view

DAWN = load_story(Path(__file__).resolve().parents[2] / "scenarios" / "dawn")


def test_heard_lines_are_grouped_by_speaker_in_order_of_first_appearance():
    lines = ["말 브람.징수관.거짓말", "말 넬.해 질 녘.참말", "말 브람.독미나리.참말"]
    state = {**start_state(DAWN, 0), "notebook": dict.fromkeys(lines, 1)}
    heard = make_view(DAWN, state)[0]["notebook"]["heard"]
    assert [line["id"] for line in heard] == [1, 3, 2]
