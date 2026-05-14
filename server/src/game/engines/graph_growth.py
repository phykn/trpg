from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict

from src.game.domain.graph import (
    AddEdgeChange,
    Graph,
    GraphChange,
    GraphEdge,
    GraphNode,
    SetEdgePropertyChange,
    SetNodePropertyChange,
    apply_graph_change,
)
from src.game.domain.graph_query import edges_from
from src.game.engines.growth import xp_for_next_level
from src.game.rules import RULES


GrowthKind = Literal["xp_grant", "level_up", "skill_learn", "skill_upgrade"]


class LevelGrowthChoice(TypedDict):
    kind: Literal["max_hp", "max_mp"]


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
    growth: LevelGrowthChoice,
) -> GraphGrowthResult:
    character, changes = _plan_level_progression(graph, character_id)
    kind = growth["kind"]
    if kind == "max_hp":
        max_hp = _int_prop(character, "max_hp")
        if max_hp >= 10:
            raise GraphGrowthError("max_hp already at cap 10")
        changes.extend(
            [
                _set(character_id, "max_hp", max_hp + 1),
                _set(character_id, "hp", min(10, _int_prop(character, "hp") + 1)),
            ]
        )
    elif kind == "max_mp":
        max_mp = _int_prop(character, "max_mp")
        if max_mp >= 10:
            raise GraphGrowthError("max_mp already at cap 10")
        changes.extend(
            [
                _set(character_id, "max_mp", max_mp + 1),
                _set(character_id, "mp", min(10, _int_prop(character, "mp") + 1)),
            ]
        )
    else:
        raise GraphGrowthError(f"unknown growth kind: {kind}")

    return GraphGrowthResult(
        changes=changes,
        character_id=character_id,
        kind="level_up",
    )


def plan_skill_level_up(
    graph: Graph,
    character_id: str,
    *,
    learn_skill_id: str | None = None,
    upgrade_skill_id: str | None = None,
) -> GraphGrowthResult:
    if (learn_skill_id is None) == (upgrade_skill_id is None):
        raise GraphGrowthError("exactly one skill level-up choice is required")

    _, level_changes = _plan_level_progression(graph, character_id)
    progressed = graph
    for change in level_changes:
        progressed = apply_graph_change(progressed, change)

    if learn_skill_id is not None:
        skill_result = plan_skill_learn(progressed, character_id, learn_skill_id)
    else:
        skill_result = plan_skill_upgrade(
            progressed, character_id, upgrade_skill_id or ""
        )

    return GraphGrowthResult(
        changes=[*level_changes, *skill_result.changes],
        character_id=character_id,
        kind=skill_result.kind,
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

    known = edges_from(graph, character_id, "knows_skill")
    if len(known) >= 3:
        raise GraphGrowthError("skill slots full")
    for edge in known:
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
                    properties={"source": "learned", "tier": 1},
                ),
            )
        ],
        character_id=character_id,
        kind="skill_learn",
    )


def plan_skill_upgrade(
    graph: Graph,
    character_id: str,
    skill_id: str,
) -> GraphGrowthResult:
    _require_character(graph, character_id)
    edge = next(
        (
            candidate
            for candidate in edges_from(graph, character_id, "knows_skill")
            if candidate.to_node_id == skill_id
        ),
        None,
    )
    if edge is None:
        raise GraphGrowthError(f"character does not know skill: {skill_id}")

    tier = edge.properties.get("tier", 1)
    if not isinstance(tier, int):
        raise GraphGrowthError(f"invalid skill tier: {skill_id}")
    if tier >= 3:
        raise GraphGrowthError(f"skill already at tier 3: {skill_id}")

    return GraphGrowthResult(
        changes=[
            SetEdgePropertyChange(
                type="set_edge_property",
                edge_id=edge.id,
                path="tier",
                value=tier + 1,
            )
        ],
        character_id=character_id,
        kind="skill_upgrade",
    )


def _plan_level_progression(
    graph: Graph,
    character_id: str,
) -> tuple[GraphNode, list[GraphChange]]:
    character = _require_character(graph, character_id)
    level = _int_prop(character, "level")
    if level >= RULES.growth.max_level:
        raise GraphGrowthError(f"already at max level {RULES.growth.max_level}")

    cost = xp_for_next_level(level)
    xp_pool = _int_prop(character, "xp_pool")
    if xp_pool < cost:
        raise GraphGrowthError(f"not enough xp: have {xp_pool}, need {cost}")

    return character, [
        _set(character_id, "xp_pool", xp_pool - cost),
        _set(character_id, "level", level + 1),
    ]


def _require_character(graph: Graph, character_id: str) -> GraphNode:
    node = graph.nodes.get(character_id)
    if node is None:
        raise GraphGrowthError(f"missing character: {character_id}")
    if node.type != "character":
        raise GraphGrowthError(f"node is not a character: {character_id}")
    return node


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
