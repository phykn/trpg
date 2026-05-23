from src.llm.calls.classify.schema import ClassifyInput


def test_classify_input_carries_focused_context():
    context = {
        "mode": "exploration",
        "identity": {"location": {"id": "town", "name": "마을"}},
        "affordances": {},
        "references": {},
        "budget": {},
    }
    input_ = ClassifyInput(player_input="상인에게 말을 겁니다", context=context)

    assert input_.player_input == "상인에게 말을 겁니다"
    assert input_.context == context
    assert set(input_.model_dump()) == {"player_input", "context"}
    assert list(input_.model_dump()) == ["context", "player_input"]


def test_classify_input_round_trip_json():
    context = {
        "mode": "combat",
        "identity": {"visible_targets": [{"id": "guard_01", "name": "경비병"}]},
        "affordances": {"can_attack": ["guard_01"]},
        "references": {"recent_exchanges": []},
        "budget": {},
    }
    input_ = ClassifyInput(player_input="검을 휘두른다", context=context)

    rebuilt = ClassifyInput.model_validate_json(input_.model_dump_json())
    assert rebuilt.context == context
