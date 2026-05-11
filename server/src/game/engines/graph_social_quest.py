from typing import Literal

from pydantic import BaseModel, ConfigDict

from src.game.domain.graph import (
    AddEdgeChange,
    Graph,
    GraphChange,
    GraphEdge,
    SetEdgePropertyChange,
    SetNodePropertyChange,
)


SocialQuestKind = Literal["reason_known", "resolved", "blocked"]

QUEST_ID = "q_missing_supplies"
PLAYER_ID = "player_01"
QUARTERMASTER_ID = "quartermaster_npc"
RESIDENT_ID = "village_resident"
GUIDE_ID = "guide_npc"
HELPED_QUIETLY_FLAG = "helped_quietly"


class SocialQuestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: SocialQuestKind
    changes: list[GraphChange]
    message_key: str
    route: str | None = None


def plan_social_quest_speak(
    graph: Graph,
    *,
    player_id: str,
    target_id: str | None,
    how: str | None,
    player_input: str,
) -> SocialQuestResult | None:
    _ = player_input

    if player_id != PLAYER_ID:
        return None

    quest = graph.nodes.get(QUEST_ID)
    if quest is None or quest.type != "quest":
        return None
    if quest.properties.get("status") != "pending":
        return None

    if target_id == RESIDENT_ID and how == "friendly":
        return SocialQuestResult(
            kind="reason_known",
            changes=[_quest_prop("resident_reason_known", True)],
            message_key="runtime.social.missing_supplies.reason_known",
        )

    if target_id == RESIDENT_ID and how == "hostile":
        return _resolve(
            graph,
            player_id=player_id,
            route="report",
            message_key="runtime.social.missing_supplies.report",
            affinity={
                QUARTERMASTER_ID: 5,
                RESIDENT_ID: -5,
            },
        )

    if target_id == QUARTERMASTER_ID and how == "friendly":
        if quest.properties.get("resident_reason_known") is not True:
            return SocialQuestResult(
                kind="blocked",
                changes=[],
                message_key="runtime.social.missing_supplies.need_reason",
            )
        return _resolve(
            graph,
            player_id=player_id,
            route="mediate",
            message_key="runtime.social.missing_supplies.mediate",
            affinity={
                QUARTERMASTER_ID: 3,
                RESIDENT_ID: 8,
                GUIDE_ID: 5,
            },
        )

    if target_id == QUARTERMASTER_ID and how == "deceptive":
        return _resolve(
            graph,
            player_id=player_id,
            route="quiet_return",
            message_key="runtime.social.missing_supplies.quiet_return",
            affinity={RESIDENT_ID: 6},
            resident_flag=HELPED_QUIETLY_FLAG,
        )

    return None


def _resolve(
    graph: Graph,
    *,
    player_id: str,
    route: str,
    message_key: str,
    affinity: dict[str, int],
    resident_flag: str | None = None,
) -> SocialQuestResult:
    changes: list[GraphChange] = [
        _quest_prop("status", "completed"),
        _quest_prop("resolution_route", route),
    ]
    for actor_id, delta in affinity.items():
        changes.extend(_affinity_changes(graph, actor_id, player_id, delta))
    if resident_flag is not None:
        changes.extend(_flag_changes(graph, RESIDENT_ID, player_id, resident_flag))

    return SocialQuestResult(
        kind="resolved",
        changes=changes,
        message_key=message_key,
        route=route,
    )


def _quest_prop(path: str, value: object) -> SetNodePropertyChange:
    return SetNodePropertyChange(
        type="set_node_property",
        node_id=QUEST_ID,
        path=path,
        value=value,
    )


def _affinity_changes(
    graph: Graph,
    actor_id: str,
    player_id: str,
    delta: int,
) -> list[GraphChange]:
    if delta == 0:
        return []

    edge_id = _relation_edge_id(actor_id, player_id)
    edge = graph.edges.get(edge_id)
    if edge is None:
        return [
            AddEdgeChange(
                type="add_edge",
                edge=GraphEdge(
                    id=edge_id,
                    type="relation",
                    from_node_id=actor_id,
                    to_node_id=player_id,
                    properties={"affinity": delta},
                ),
            )
        ]

    current = edge.properties.get("affinity")
    current_affinity = current if isinstance(current, int) else 0
    return [
        SetEdgePropertyChange(
            type="set_edge_property",
            edge_id=edge_id,
            path="affinity",
            value=current_affinity + delta,
        )
    ]


def _flag_changes(
    graph: Graph,
    actor_id: str,
    player_id: str,
    flag: str,
) -> list[GraphChange]:
    edge_id = _relation_edge_id(actor_id, player_id)
    edge = graph.edges.get(edge_id)
    if edge is None:
        return [
            AddEdgeChange(
                type="add_edge",
                edge=GraphEdge(
                    id=edge_id,
                    type="relation",
                    from_node_id=actor_id,
                    to_node_id=player_id,
                    properties={"affinity": 0, "flags": [flag]},
                ),
            )
        ]

    raw_flags = edge.properties.get("flags")
    flags = (
        [item for item in raw_flags if isinstance(item, str)]
        if isinstance(raw_flags, list)
        else []
    )
    if flag not in flags:
        flags.append(flag)

    return [
        SetEdgePropertyChange(
            type="set_edge_property",
            edge_id=edge_id,
            path="flags",
            value=flags,
        )
    ]


def _relation_edge_id(actor_id: str, player_id: str) -> str:
    return f"relation:{actor_id}:{player_id}"
