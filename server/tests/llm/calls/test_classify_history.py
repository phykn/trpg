"""ClassifyInput carries context for pronoun and surprise resolution."""

from src.llm.calls.classify.schema import ClassifyInput


def test_classify_input_defaults_history_dialogue_empty():
    input_ = ClassifyInput(player_input="공격", surroundings={})
    assert input_.history == []
    assert input_.recent_dialogue == []


def test_classify_input_carries_history_and_dialogue():
    history = [
        {"turn": 1, "target": "goblin_01", "summary": "수학 문제로 정신을 분산시킴"},
        {"turn": 2, "target": None, "summary": "조용히 접근"},
    ]
    dialogue = [
        {"turn": 1, "player": "잠깐, 5+7은?", "narrator": "고블린이 머리를 긁는다"},
    ]
    input_ = ClassifyInput(
        player_input="지금 친다",
        surroundings={"location": {"id": "x"}, "entities": []},
        history=history,
        recent_dialogue=dialogue,
    )
    assert input_.history == history
    assert input_.recent_dialogue == dialogue


def test_classify_input_round_trip_json():
    history = [{"turn": 3, "target": "guard_01", "summary": "잠든 경비병 확인"}]
    input_ = ClassifyInput(
        player_input="검을 휘두른다",
        surroundings={"location": {"id": "x"}},
        history=history,
        recent_dialogue=[],
    )
    rebuilt = ClassifyInput.model_validate_json(input_.model_dump_json())
    assert rebuilt.history == history
    assert rebuilt.recent_dialogue == []
