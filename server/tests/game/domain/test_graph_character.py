from src.game.domain.graph import GraphNode
from src.game.domain.graph_character import (
    can_character_fight,
    graph_character_kind,
    is_visible_character,
)


def _character(**properties) -> GraphNode:
    return GraphNode(
        id="char_01",
        type="character",
        properties={
            "hp": 10,
            "max_hp": 10,
            "alive": True,
            "status": [],
            **properties,
        },
    )


def test_character_visibility_excludes_defeated_characters():
    assert is_visible_character(_character()) is True
    assert is_visible_character(_character(hp=0, status=["defeated"])) is False
    assert is_visible_character(_character(alive=False)) is False


def test_can_character_fight_requires_live_positive_hp():
    assert can_character_fight(_character()) is True
    assert can_character_fight(_character(hp=0)) is False
    assert can_character_fight(_character(max_hp=0)) is False


def test_graph_character_kind_uses_enemy_markers():
    assert graph_character_kind(_character(xp_reward=1)) == "enemy"
    assert (
        graph_character_kind(_character(combat_behavior={"attack_priority": "nearest"}))
        == "enemy"
    )
    assert graph_character_kind(_character()) == "npc"
