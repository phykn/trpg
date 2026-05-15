from typing import Literal

from .models import GraphNode


GraphCharacterKind = Literal["npc"]


def can_character_fight(node: GraphNode) -> bool:
    if node.type != "character" or node.properties.get("alive") is False:
        return False
    status = node.properties.get("status", [])
    return not (isinstance(status, list) and "dead" in status)


def is_visible_character(node: GraphNode) -> bool:
    return can_character_fight(node)


def graph_character_kind(node: GraphNode) -> GraphCharacterKind:
    del node
    return "npc"
