"""_run_verb_chain — multi-verb chain dispatch 단위 검증.

list[Verb] 직접 처리: tail attack/cast → combat phase entry, prefix verb는
emit_* 핸들러 또는 narrate 흡수."""

import inspect

from src.flow import turn as turn_module


def test_run_verb_chain_signature():
    sig = inspect.signature(turn_module._run_verb_chain)
    params = list(sig.parameters.items())
    assert params[0][0] == "verbs"
    keyword_params = [name for name, p in params[1:]
                      if p.kind == inspect.Parameter.KEYWORD_ONLY]
    for required in ("client", "state", "scenario_repo", "save_repo",
                       "dirty", "rng", "to_front_fn", "player_input", "graph"):
        assert required in keyword_params


def test_run_verb_chain_separates_tail_combat_from_prefix():
    src = inspect.getsource(turn_module._run_verb_chain)
    assert 'tail_combat' in src
    # Stage 1b: tail attack만 combat entry. cast는 narrate-only (단일 cast와 같은
    # 정책, 자해 진입 회피).
    assert 'verbs[-1].name == "attack"' in src
    assert 'prefix = verbs[:-1] if tail_combat is not None else list(verbs)' in src


def test_run_verb_chain_pre_move_snapshot_uses_verb_name():
    """pre_move snapshot이 p.name == "move" 호환으로 동작하는지."""
    src = inspect.getsource(turn_module._run_verb_chain)
    assert 'any(p.name == "move" for p in prefix)' in src


def test_run_verb_chain_emit_loop_uses_emit_verb_in_chain():
    src = inspect.getsource(turn_module._run_verb_chain)
    assert "_emit_verb_in_chain(client, state, dirty, verb)" in src


def test_run_verb_chain_handles_engine_fail_signal():
    src = inspect.getsource(turn_module._run_verb_chain)
    assert "_engine_fail" in src
    assert "chain_failure_raws.append" in src
    assert "part_failures[idx] = True" in src


def test_run_verb_chain_collects_act_evts():
    src = inspect.getsource(turn_module._run_verb_chain)
    assert "chain_act_evts.append((ev, idx))" in src
    assert "chain_act_lines.append(text)" in src


def test_run_verb_chain_combat_tail_path_has_invalid_target_guard():
    src = inspect.getsource(turn_module._run_verb_chain)
    assert "has_invalid_combat_targets" in src
    assert "NO_COMBAT_TARGETS_TEXT" in src


def test_run_verb_chain_combat_tail_calls_enter_combat():
    src = inspect.getsource(turn_module._run_verb_chain)
    assert "_enter_combat_and_finalize" in src


def test_run_verb_chain_narrate_decision_uses_chain_needs_narrate():
    src = inspect.getsource(turn_module._run_verb_chain)
    assert "_chain_needs_narrate(state, prefix, part_failures, pre_move_visited)" in src
    assert "is_dramatic_fail" in src


def test_run_verb_chain_skips_emit_for_narrate_absorb_verbs():
    """speak/perceive/alter/cast/attack는 chain prefix에서 emit_* 호출 안 함 —
    narrate가 prose 흡수. cast/attack은 prefix 위치에서 phase-changing 의도
    아니므로 _emit_verb_in_chain의 ValueError raise를 회피."""
    src = inspect.getsource(turn_module._run_verb_chain)
    assert 'verb.name in ("speak", "perceive", "alter", "cast", "attack")' in src
    # 이 분기가 _emit_verb_in_chain 호출 전에 와야 함 (continue로 skip)
    branch_idx = src.find('verb.name in ("speak", "perceive", "alter", "cast", "attack")')
    emit_call_idx = src.find("_emit_verb_in_chain(client, state, dirty, verb)")
    assert branch_idx < emit_call_idx


def test_run_verb_chain_synthesizes_wait_when_no_explicit_wait():
    src = inspect.getsource(turn_module._run_verb_chain)
    assert 'narrate_action = last_wait if last_wait is not None else Verb(name="wait")' in src


def test_run_verb_chain_finalize_at_end():
    src = inspect.getsource(turn_module._run_verb_chain)
    assert "finalize(state, save_repo, dirty, to_front_fn)" in src
    assert "tick_turn_buffs(state, dirty)" in src


def test_run_verb_chain_pin_subject_by_input_name_when_move():
    """move 포함 chain에서 pin_subject_by_input_name 호출."""
    src = inspect.getsource(turn_module._run_verb_chain)
    assert 'any(p.name == "move" for p in prefix)' in src
    assert "pin_subject_by_input_name" in src


def test_run_verb_chain_keep_move_card_drops_others():
    """tail combat path에서 move 카드만 keep, 나머지 drop_pushed_act."""
    src = inspect.getsource(turn_module._run_verb_chain)
    assert 'prefix[part_idx].name == "move"' in src
    assert "drop_pushed_act" in src
