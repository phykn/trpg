"""NPC-touching verbs (transfer mode=trade or gift to NPC) re-engage narrate even
though they mutate state.

Receipt-only verbs (transfer equip|unequip / use / rest) are pure inventory shuffles —
narrate adds nothing. But mode=trade or mode=gift to/from NPC involve a second
character's reaction; without a narrate beat the engine card is the only signal of
that interaction and the NPC reads as inert.

Stage 1b verb-direct: receipt 분기는 verb 인스턴스 + `_is_receipt` 검증."""

from src.game.flow.turn import _is_receipt
from src.llm.calls.classify.schema import Verb


def test_buy_verb_is_not_receipt(fresh_state):
    """transfer(mode=trade, NPC→player) is buy — narrate-worthy (NPC reaction)."""
    verb = Verb(
        name="transfer",
        modifiers={
            "from_id": "npc_01",
            "to_id": "player_01",
            "mode": "trade",
            "item_id": "item_01",
        },
    )
    assert not _is_receipt(fresh_state, verb)


def test_sell_verb_is_not_receipt(fresh_state):
    """transfer(mode=trade, player→NPC) is sell — narrate-worthy."""
    verb = Verb(
        name="transfer",
        modifiers={
            "from_id": "player_01",
            "to_id": "npc_01",
            "mode": "trade",
            "item_id": "item_01",
        },
    )
    assert not _is_receipt(fresh_state, verb)


def test_give_verb_is_not_receipt(fresh_state):
    """transfer(mode=gift, player→NPC) is give — narrate-worthy."""
    verb = Verb(
        name="transfer",
        modifiers={
            "from_id": "player_01",
            "to_id": "npc_01",
            "mode": "gift",
            "item_id": "item_01",
        },
    )
    assert not _is_receipt(fresh_state, verb)


def test_equip_verb_is_receipt(fresh_state):
    """transfer(equip slot)은 receipt — narrate skip."""
    verb = Verb(
        name="transfer",
        modifiers={
            "from_id": "<self>.inventory",
            "to_id": "<self>.equipped.weapon",
            "mode": "gift",
            "item_id": "sword_01",
        },
    )
    assert _is_receipt(fresh_state, verb)


def test_unequip_verb_is_receipt(fresh_state):
    verb = Verb(
        name="transfer",
        modifiers={
            "from_id": "<self>.equipped.weapon",
            "to_id": "<self>.inventory",
            "mode": "gift",
            "item_id": "sword_01",
        },
    )
    assert _is_receipt(fresh_state, verb)


def test_use_verb_is_receipt(fresh_state):
    verb = Verb(name="use", modifiers={"item_id": "potion_01"})
    assert _is_receipt(fresh_state, verb)


def test_wait_verb_not_receipt(fresh_state):
    """wait는 narrate-worthy (idle / fluff)."""
    verb = Verb(name="wait")
    assert not _is_receipt(fresh_state, verb)
