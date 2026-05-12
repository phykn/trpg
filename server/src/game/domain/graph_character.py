from typing import Literal

from .graph import GraphNode


GraphCharacterKind = Literal["npc", "enemy"]


def can_character_fight(node: GraphNode) -> bool:
    if node.type != "character" or node.properties.get("alive") is False:
        return False
    status = node.properties.get("status", [])
    return not (
        isinstance(status, list)
        and any(item in {"defeated", "downed"} for item in status)
    )


def is_visible_character(node: GraphNode) -> bool:
    return can_character_fight(node)


def graph_character_kind(node: GraphNode) -> GraphCharacterKind:
    if _int_prop_default(node, "xp_reward", 0) > 0:
        return "enemy"
    if node.properties.get("combat_behavior") is not None:
        return "enemy"
    return "npc"


def _int_prop_default(node: GraphNode, key: str, default: int) -> int:
    value = node.properties.get(key)
    return value if isinstance(value, int) else default
