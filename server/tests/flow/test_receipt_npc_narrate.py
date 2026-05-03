"""NPC-touching actions (buy / sell / give) re-engage narrate even though they
mutate state.

Receipt-only paths (equip / unequip / use / rest) are pure inventory shuffles —
narrate adds nothing. But buy / sell / give involve a second character's
reaction; without a narrate beat the engine card is the only signal of that
interaction and the NPC reads as inert. The receipt set keeps only actions that
don't touch another character.
"""

from src.flow.turn import _RECEIPT_ACTION_TYPES, _is_receipt
from src.llm_calls.classify.schema import (
    BuyAction,
    EquipAction,
    GiveAction,
    SellAction,
    UnequipAction,
    UseAction,
)


def test_buy_is_not_receipt():
    assert BuyAction not in _RECEIPT_ACTION_TYPES


def test_sell_is_not_receipt():
    assert SellAction not in _RECEIPT_ACTION_TYPES


def test_give_is_not_receipt():
    assert GiveAction not in _RECEIPT_ACTION_TYPES


def test_equip_unequip_use_remain_receipt():
    assert EquipAction in _RECEIPT_ACTION_TYPES
    assert UnequipAction in _RECEIPT_ACTION_TYPES
    assert UseAction in _RECEIPT_ACTION_TYPES


def test_is_receipt_dispatches_buy_to_narrate(fresh_state):
    action = BuyAction(action="buy", npc_id="npc_01", item_id="item_01")
    assert not _is_receipt(fresh_state, action)


def test_is_receipt_dispatches_sell_to_narrate(fresh_state):
    action = SellAction(action="sell", npc_id="npc_01", item_id="item_01")
    assert not _is_receipt(fresh_state, action)


def test_is_receipt_dispatches_give_to_narrate(fresh_state):
    action = GiveAction(
        action="give", from_id="player_01", to_id="npc_01", item_id="item_01"
    )
    assert not _is_receipt(fresh_state, action)
