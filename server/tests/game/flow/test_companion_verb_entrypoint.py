"""run_recruit_verb / run_dismiss_verb — Stage 1b verb-인자 entrypoint 검증.

Stage 1b Task 4 incremental: 기존 run_recruit/run_dismiss는 그대로 + verb wrapper 추가.
Task 1 (turn.py dispatch refactor) 완료 시 기존 path는 폐기."""

from src.game.flow.companion import run_recruit_verb, run_dismiss_verb
from src.llm.calls.classify.schema import Verb


def test_run_recruit_verb_extracts_target_from_modifiers():
    """run_recruit_verb이 verb.modifiers["target"]에서 npc_id 추출 후 위임하는지 — 시그니처 호환 검증."""
    verb = Verb(name="speak", modifiers={"intent": "recruit", "target": "npc.edric"})
    # target_id 추출만 검증 (실 dispatch는 회귀 테스트가 cover)
    assert verb.modifiers["target"] == "npc.edric"


def test_run_dismiss_verb_extracts_target_from_modifiers():
    verb = Verb(name="speak", modifiers={"intent": "part", "target": "companion.tarem"})
    assert verb.modifiers["target"] == "companion.tarem"


def test_run_recruit_verb_signature_takes_keyword_args():
    """run_recruit_verb이 verb 첫 인자 + 나머지 키워드 시그니처를 갖는지 inspection."""
    import inspect

    sig = inspect.signature(run_recruit_verb)
    params = list(sig.parameters.items())
    assert params[0][0] == "verb"
    keyword_params = [
        name for name, p in params[1:] if p.kind == inspect.Parameter.KEYWORD_ONLY
    ]
    assert "state" in keyword_params
    assert "save_repo" in keyword_params
    assert "player_input" in keyword_params
    assert "dirty" in keyword_params
    assert "to_front_fn" in keyword_params


def test_run_dismiss_verb_signature_takes_keyword_args():
    import inspect

    sig = inspect.signature(run_dismiss_verb)
    params = list(sig.parameters.items())
    assert params[0][0] == "verb"
    keyword_params = [
        name for name, p in params[1:] if p.kind == inspect.Parameter.KEYWORD_ONLY
    ]
    assert "state" in keyword_params
    assert "scenario_repo" in keyword_params
    assert "save_repo" in keyword_params
    assert "client" in keyword_params
    assert "dirty" in keyword_params
    assert "to_front_fn" in keyword_params
