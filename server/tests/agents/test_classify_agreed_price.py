"""BuyAction / SellAction agreed_price field — schema-only validation."""

import pytest
from pydantic import ValidationError

from src.llm_calls.classify.schema import BuyAction, SellAction


def test_buy_action_with_agreed_price():
    a = BuyAction(action="buy", npc_id="n", item_id="i", agreed_price=2)
    assert a.agreed_price == 2


def test_buy_action_default_none():
    a = BuyAction(action="buy", npc_id="n", item_id="i")
    assert a.agreed_price is None


def test_sell_action_with_agreed_price():
    a = SellAction(action="sell", npc_id="n", item_id="i", agreed_price=5)
    assert a.agreed_price == 5


def test_sell_action_default_none():
    a = SellAction(action="sell", npc_id="n", item_id="i")
    assert a.agreed_price is None


def test_buy_action_zero_price_allowed():
    a = BuyAction(action="buy", npc_id="n", item_id="i", agreed_price=0)
    assert a.agreed_price == 0


def test_buy_action_negative_price_rejected():
    with pytest.raises(ValidationError):
        BuyAction(action="buy", npc_id="n", item_id="i", agreed_price=-1)


def test_sell_action_negative_price_rejected():
    with pytest.raises(ValidationError):
        SellAction(action="sell", npc_id="n", item_id="i", agreed_price=-1)
