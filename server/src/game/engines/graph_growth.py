from typing import Literal

from pydantic import BaseModel, ConfigDict

from src.game.domain.graph import (
    AddEdgeChange,
    Graph,
    GraphChange,
    GraphEdge,
    GraphNode,
    SetNodePropertyChange,
)
from src.game.domain.graph_query import edges_from
from src.game.domain.types import GRAPH_STAT_KEYS, GraphStatKey
from src.game.engines.growth import calc_max_hp, calc_max_mp, xp_for_next_level
from src.game.rules import RULES


GrowthKind = Literal["xp_grant", "level_up", "skill_learn"]


class GraphGrowthError(ValueError):
    pass


class GraphGrowthResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changes: list[GraphChange]
    character_id: str
    kind: GrowthKind


def plan_xp_grant(
    graph: Graph,
    character_id: str,
    amount: int,
) -> GraphGrowthResult:
    character = _require_character(graph, character_id)
    if amount < 0:
        raise GraphGrowthError(f"xp grant must be non-negative: {amount}")
    current = _int_prop(character, "xp_pool")
    return GraphGrowthResult(
        changes=[_set(character_id, "xp_pool", current + amount)],
        character_id=character_id,
        kind="xp_grant",
    )


def plan_level_up(
    graph: Graph,
    character_id: str,
    stat_up: GraphStatKey,
) -> GraphGrowthResult:
    character = _require_character(graph, character_id)
    level = _int_prop(character, "level")
    if level >= RULES.growth.max_level:
        raise GraphGrowthError(f"already at max level {RULES.growth.max_level}")

    cost = xp_for_next_level(level)
    xp_pool = _int_prop(character, "xp_pool")
    if xp_pool < cost:
        raise GraphGrowthError(f"not enough xp: have {xp_pool}, need {cost}")

    if stat_up not in GRAPH_STAT_KEYS:
        raise GraphGrowthError(f"invalid stat_up: {stat_up}")
    stats = _stats(character)
    up_value = _stat_value(stats, stat_up)
    if up_value >= 20:
        raise GraphGrowthError(f"{stat_up} already at cap 20")

    next_level = level + 1
    next_stats = dict(stats)
    next_stats[stat_up] = up_value + 1
    max_hp = calc_max_hp(next_level, next_stats["body"])
    max_mp = calc_max_mp(next_level, next_stats["mind"])
    hp = min(_int_prop(character, "hp"), max_hp)
    mp = min(_int_prop(character, "mp"), max_mp)

    return GraphGrowthResult(
        changes=[
            _set(character_id, "xp_pool", xp_pool - cost),
            _set(character_id, "level", next_level),
            _set(character_id, f"stats.{stat_up}", next_stats[stat_up]),
            _set(character_id, "max_hp", max_hp),
            _set(character_id, "max_mp", max_mp),
            _set(character_id, "hp", hp),
            _set(character_id, "mp", mp),
        ],
        character_id=character_id,
        kind="level_up",
    )


def plan_skill_learn(
    graph: Graph,
    character_id: str,
    skill_id: str,
) -> GraphGrowthResult:
    _require_character(graph, character_id)
    skill = graph.nodes.get(skill_id)
    if skill is None:
        raise GraphGrowthError(f"missing skill: {skill_id}")
    if skill.type != "skill":
        raise GraphGrowthError(f"node is not a skill: {skill_id}")
    for edge in edges_from(graph, character_id, "knows_skill"):
        if edge.to_node_id == skill_id:
            raise GraphGrowthError(f"character already knows skill: {skill_id}")

    return GraphGrowthResult(
        changes=[
            AddEdgeChange(
                type="add_edge",
                edge=GraphEdge(
                    id=f"knows_skill:learned:{character_id}:{skill_id}",
                    type="knows_skill",
                    from_node_id=character_id,
                    to_node_id=skill_id,
                    properties={"source": "learned"},
                ),
            )
        ],
        character_id=character_id,
        kind="skill_learn",
    )


def _require_character(graph: Graph, character_id: str) -> GraphNode:
    node = graph.nodes.get(character_id)
    if node is None:
        raise GraphGrowthError(f"missing character: {character_id}")
    if node.type != "character":
        raise GraphGrowthError(f"node is not a character: {character_id}")
    return node


def _stats(character: GraphNode) -> dict[str, int]:
    raw = character.properties.get("stats")
    if not isinstance(raw, dict):
        raise GraphGrowthError(f"missing stats: {character.id}")
    return {key: _stat_value(raw, key) for key in GRAPH_STAT_KEYS}


def _stat_value(stats: dict, key: str) -> int:
    value = stats.get(key)
    if not isinstance(value, int):
        raise GraphGrowthError(f"missing numeric stat: {key}")
    return value


def _int_prop(character: GraphNode, key: str) -> int:
    value = character.properties.get(key)
    if not isinstance(value, int):
        raise GraphGrowthError(f"missing numeric property {character.id}.{key}")
    return value


def _set(node_id: str, path: str, value: int) -> SetNodePropertyChange:
    return SetNodePropertyChange(
        type="set_node_property",
        node_id=node_id,
        path=path,
        value=value,
    )
