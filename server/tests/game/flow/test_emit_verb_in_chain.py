"""_emit_verb_in_chain — chain prefix dispatch 동작 검증.

chain-incompat verb (wait/perceive/speak/cast/attack/rest)이 prefix 위치에
들어왔을 때 ValueError를 raise하는지만 검증. 정상 verb (use/move/transfer)의
emit dispatch는 chain 통합 테스트(test_chain_*.py)가 커버."""

import pytest

from src.game.flow.chain import _emit_verb_in_chain
from src.llm.calls.classify.schema import Verb


def test_emit_verb_in_chain_raises_for_attack():
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
