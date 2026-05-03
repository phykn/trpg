"""Verify dead entity's loot transfers to the killer."""

from server.src.engines.combat import transfer_loot_on_death
from server.src.domain.entities import Character


def _make_char(id_: str, inventory_ids: list[str], gold: int) -> Character:
    return Character.model_construct(
        id=id_,
        name=id_,
        race_id="human",
        inventory_ids=list(inventory_ids),
        gold=gold,
    )


def test_dead_entity_loot_to_killer():
    """inventory_ids + gold move from dead to winner."""
    dead = _make_char("enemy", ["녹슨 도끼", "조잡한 가죽 조끼"], 5)
    winner = _make_char("player", ["정찰병의 단검"], 15)
    transfer_loot_on_death(dead=dead, winner=winner)
    assert "녹슨 도끼" in winner.inventory_ids
    assert "조잡한 가죽 조끼" in winner.inventory_ids
    assert winner.gold == 20
    assert dead.inventory_ids == []
    assert dead.gold == 0


def test_empty_inventory_no_op():
    """Empty inventory + zero gold → no error, winner unchanged."""
    dead = _make_char("enemy", [], 0)
    winner = _make_char("player", ["x"], 1)
    transfer_loot_on_death(dead=dead, winner=winner)
    assert winner.inventory_ids == ["x"]
    assert winner.gold == 1


def test_gold_only_transfer():
    """No inventory items, only gold transfers."""
    dead = _make_char("enemy", [], 50)
    winner = _make_char("player", [], 10)
    transfer_loot_on_death(dead=dead, winner=winner)
    assert winner.gold == 60
    assert dead.gold == 0
    assert winner.inventory_ids == []
