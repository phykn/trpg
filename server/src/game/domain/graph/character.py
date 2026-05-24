from typing import Literal

from .models import GraphNode


GraphCharacterKind = Literal["npc"]


def can_character_fight(node: GraphNode) -> bool:
    if node.type != "character" or node.properties.get("alive") is False:
        return False
    status = node.properties.get("status", [])
    return not (isinstance(status, list) and "dead" in status)


def can_character_be_attacked(node: GraphNode) -> bool:
    return can_character_fight(node) and node.properties.get("protected") is not True


def is_visible_character(node: GraphNode) -> bool:
    return can_character_fight(node)


def graph_character_kind(node: GraphNode) -> GraphCharacterKind:
    del node
    return "npc"
