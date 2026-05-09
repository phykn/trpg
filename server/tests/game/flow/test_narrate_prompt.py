from src.llm.calls.narrate.schema import NarrateInput


def _base_input(**kwargs) -> NarrateInput:
    defaults = dict(
        world="테스트 세계",
        session={},
        history="",
        player_view={},
        surroundings={},
        judge_result={"action": "pass"},
        player_input="에드릭에게 보고합니다",
    )
    defaults.update(kwargs)
    return NarrateInput(**defaults)


def test_narrate_prompt_includes_recent_combat_result():
    """Recent combat events surface in the serialized prompt body."""
    recent_events = [
        {
            "type": "combat",
            "summary": "고블린 약탈자에게 27 피해, 적 HP 7/34로 도주. 주인공 19 피해, HP 1/20.",
        }
    ]
    inp = _base_input(recent_engine_events=recent_events)
    serialized = inp.model_dump_json()
    assert "고블린" in serialized
    assert "27 피해" in serialized
    assert ("도주" in serialized) or ("HP 7" in serialized)


def test_narrate_prompt_no_events_when_empty():
    """Empty events list → field present but empty, no events-block prefix needed."""
    inp = _base_input(
        player_input="광장에서 주변을 둘러봅니다",
        recent_engine_events=[],
    )
    serialized = inp.model_dump_json()
    # empty list serializes as "[]" — no event summary text
    assert "직전 turn" not in serialized


def test_narrate_prompt_default_is_empty_list():
    """NarrateInput with no recent_engine_events defaults to empty list."""
    inp = _base_input()
    assert inp.recent_engine_events == []


def test_narrate_prompt_omit_none_still_empty():
    """Passing None is treated as empty (via validator or default)."""
    inp = NarrateInput(
        world="w",
        session={},
        history="",
        player_view={},
        surroundings={},
        judge_result={"action": "pass"},
        player_input="test",
        recent_engine_events=None,
    )
    # Should not raise; coerced to [] or None; either way no summary text leaks
    serialized = inp.model_dump_json()
    assert "직전 turn" not in serialized
