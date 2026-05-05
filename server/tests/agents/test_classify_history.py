"""JudgeInput carries history + recent_dialogue so classify can resolve
pronouns ("그것을 든다") and detect surprise build-up. Defaults are empty
lists when no prior context exists (game start)."""

from src.llm.calls.classify.schema import JudgeInput


def test_judge_input_defaults_history_dialogue_empty():
    j = JudgeInput(player_input="공격", surroundings={})
    assert j.history == []
    assert j.recent_dialogue == []


def test_judge_input_carries_history_and_dialogue():
    history = [
        {"turn": 1, "target": "goblin_01", "summary": "수학 문제로 정신을 분산시킴"},
        {"turn": 2, "target": None, "summary": "조용히 접근"},
    ]
    dialogue = [
        {"turn": 1, "player": "잠깐, 5+7은?", "narrator": "고블린이 머리를 긁는다"},
    ]
    j = JudgeInput(
        player_input="지금 친다",
        surroundings={"location": {"id": "x"}, "entities": []},
        history=history,
        recent_dialogue=dialogue,
    )
    assert j.history == history
    assert j.recent_dialogue == dialogue


def test_judge_input_round_trip_json():
    """JudgeInput serializes via model_dump_json (the runner ships this string
    to the LLM); fields must survive round-trip without loss."""
    history = [{"turn": 3, "target": "guard_01", "summary": "잠든 경비병 확인"}]
    j = JudgeInput(
        player_input="검을 휘두른다",
        surroundings={"location": {"id": "x"}},
        history=history,
        recent_dialogue=[],
    )
    rebuilt = JudgeInput.model_validate_json(j.model_dump_json())
    assert rebuilt.history == history
    assert rebuilt.recent_dialogue == []
