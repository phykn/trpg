"""_emit_verb_in_chain — chain 내부 verb dispatch 단위 검증.

Stage 1b Task 1 Step 3 사전 작업: multi-verb chain refactor 시 prefix verb를
emit_* 핸들러로 보내는 dispatcher의 동작 검증."""

import inspect

import pytest

from src.game.flow.chain import _emit_verb_in_chain, _resolve_transfer_emit
from src.llm.calls.classify.schema import Verb


def test_emit_verb_in_chain_signature():
    """_emit_verb_in_chain(client, state, dirty, verb) 시그니처."""
    sig = inspect.signature(_emit_verb_in_chain)
    params = list(sig.parameters)
    assert params == ["client", "state", "dirty", "verb"]


def test_emit_verb_in_chain_handles_compat_verbs():
    """소스 inspection — chain-compat verb (use/move/transfer) 모두 분기 포함."""
    src = inspect.getsource(_emit_verb_in_chain)
    for verb_name in ("use", "move", "transfer"):
        assert f'n == "{verb_name}"' in src, (
            f"_emit_verb_in_chain missing branch: {verb_name}"
        )


def test_emit_verb_in_chain_transfer_branches_4_paths():
    """transfer가 equip/unequip/gift/buy/sell 5 path로 분기 — 공통 helper로 위임."""
    chain_src = inspect.getsource(_emit_verb_in_chain)
    assert "_resolve_transfer_emit(" in chain_src
    helper_src = inspect.getsource(_resolve_transfer_emit)
    assert "<self>.equipped" in helper_src
    assert "emit_equip" in helper_src
    assert "emit_unequip" in helper_src
    assert "emit_give" in helper_src
    assert 'mode == "gift"' in helper_src
    assert "emit_trade" in helper_src
    assert 'direction="sell"' in helper_src
    assert 'direction="buy"' in helper_src


def test_emit_verb_in_chain_rejects_non_compat_verbs():
    """wait/perceive/speak/cast/attack/rest는 chain 안에서 emit 불가."""
    src = inspect.getsource(_emit_verb_in_chain)
    assert "raise ValueError" in src
    assert "cannot be emitted in chain" in src


def test_emit_verb_in_chain_raises_for_attack():
    """attack은 chain prefix에서 emit 불가 — outer가 _dispatch_verb 직접 호출."""
    verb = Verb(name="attack", target_ids=["g_01"])
    with pytest.raises(ValueError, match="cannot be emitted in chain"):
        _emit_verb_in_chain(client=None, state=None, dirty=None, verb=verb)


def test_emit_verb_in_chain_raises_for_wait():
    verb = Verb(name="wait")
    with pytest.raises(ValueError, match="cannot be emitted in chain"):
        _emit_verb_in_chain(client=None, state=None, dirty=None, verb=verb)


def test_emit_verb_in_chain_raises_for_speak():
    verb = Verb(name="speak", modifiers={"intent": "friendly", "target": "n_01"})
    with pytest.raises(ValueError, match="cannot be emitted in chain"):
        _emit_verb_in_chain(client=None, state=None, dirty=None, verb=verb)


def test_emit_verb_in_chain_raises_for_rest():
    verb = Verb(name="rest")
    with pytest.raises(ValueError, match="cannot be emitted in chain"):
        _emit_verb_in_chain(client=None, state=None, dirty=None, verb=verb)
