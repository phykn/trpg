"""_dispatch_verb 단위 테스트 — Stage 1b Task 1 Step 2 신규 함수.

Stage 1a 어댑터가 verb→legacy 변환 후 기존 _dispatch가 처리하는 path가 main이고,
_dispatch_verb은 Task 1 outer loop refactor 전까지 dead code. 본 테스트는 함수
signature와 verb name dispatch 분기 본문이 잘못 깨지지 않는지 검증."""

import inspect

from src.game.flow import turn as turn_module


def test_dispatch_verb_signature_takes_keyword_args():
    sig = inspect.signature(turn_module._dispatch_verb)
    params = list(sig.parameters.items())
    assert params[0][0] == "verb"
    keyword_params = [name for name, p in params[1:]
                      if p.kind == inspect.Parameter.KEYWORD_ONLY]
    for required in ("client", "state", "scenario_repo", "save_repo",
                       "dirty", "rng", "to_front_fn", "player_input", "graph"):
        assert required in keyword_params, f"missing kwarg: {required}"


def test_dispatch_verb_handles_all_nine_verbs():
    """소스 inspection: _dispatch_verb이 9개 verb name 모두에 대해 분기를 갖는지."""
    src = inspect.getsource(turn_module._dispatch_verb)
    for verb_name in ("move", "transfer", "use", "attack", "cast",
                        "speak", "perceive", "rest", "wait"):
        assert f'name == "{verb_name}"' in src, f"_dispatch_verb missing branch: {verb_name}"


def test_dispatch_verb_speak_recruit_dispatches_to_companion():
    """speak(intent=recruit) 분기가 companion.run_recruit_verb 호출하는지."""
    src = inspect.getsource(turn_module._dispatch_verb)
    assert 'intent == "recruit"' in src
    assert "run_recruit_verb" in src


def test_dispatch_verb_speak_part_dispatches_to_companion():
    src = inspect.getsource(turn_module._dispatch_verb)
    assert 'intent == "part"' in src
    assert "run_dismiss_verb" in src


def test_dispatch_verb_attack_uses_invalid_targets_guard():
    """attack 분기가 has_invalid_combat_targets로 가드하는지."""
    src = inspect.getsource(turn_module._dispatch_verb)
    assert "has_invalid_combat_targets" in src


def test_dispatch_verb_attack_calls_enter_combat():
    src = inspect.getsource(turn_module._dispatch_verb)
    assert "_enter_combat_and_finalize" in src


def test_dispatch_verb_transfer_branches_equip_unequip_gift_trade():
    # transfer 분기 4 path는 공통 helper에 있고, _dispatch_verb는 그것을 호출
    dispatch_src = inspect.getsource(turn_module._dispatch_verb)
    assert "_resolve_transfer_emit(" in dispatch_src
    helper_src = inspect.getsource(turn_module._resolve_transfer_emit)
    assert 'mode == "gift"' in helper_src
    assert "<self>.equipped" in helper_src
    assert "emit_equip" in helper_src
    assert "emit_unequip" in helper_src
    assert "emit_give" in helper_src
    assert "emit_trade" in helper_src


def test_dispatch_verb_cast_routes_through_emit_cast():
    """cast(heal/buff) → emit_cast via _run_one_step_action. 전투 진입 없음
    (heal/buff는 자가/동료 시전 — 적대 행위 아님). 미존재/비-heal-buff skill은
    semantic check이 1차 거름, 거기 슬리든 케이스만 narrate fallback."""
    src = inspect.getsource(turn_module._dispatch_verb)
    cast_section_start = src.find('name == "cast"')
    cast_section_end = src.find('name == "rest"', cast_section_start)
    cast_section = src[cast_section_start:cast_section_end]
    assert "_enter_combat_and_finalize" not in cast_section
    assert "emit_cast" in cast_section
    assert "_run_one_step_action" in cast_section
    # narrate fallback (defensive — semantic check should catch this first)
    assert "stream_narrate_tail" in cast_section


def test_dispatch_verb_unknown_verb_raises():
    src = inspect.getsource(turn_module._dispatch_verb)
    assert 'raise ValueError(f"unknown verb name' in src
