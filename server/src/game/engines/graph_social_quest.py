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
ELIGIBLE_STATUSES = {"locked", "pending", "active"}


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
    if player_id != PLAYER_ID:
        return None

    quest = graph.nodes.get(QUEST_ID)
    if quest is None or quest.type != "quest":
        return None
    if quest.properties.get("status") not in ELIGIBLE_STATUSES:
        return None

    if target_id == RESIDENT_ID and how == "friendly" and _mentions_reason(player_input):
        if quest.properties.get("resident_reason_known") is True:
            return None
        return SocialQuestResult(
            kind="reason_known",
            changes=[
                _quest_prop("resident_reason_known", True),
                *_relation_changes(graph, RESIDENT_ID, player_id, affinity_delta=2),
            ],
            message_key="runtime.social.missing_supplies.reason_known",
        )

    if target_id == RESIDENT_ID and how == "hostile" and _mentions_report(player_input):
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

    if target_id == QUARTERMASTER_ID and how == "friendly" and _mentions_mediate(player_input):
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

    if how == "deceptive" and _mentions_quiet_return(player_input):
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
        if actor_id == RESIDENT_ID and resident_flag is not None:
            continue
        changes.extend(_relation_changes(graph, actor_id, player_id, affinity_delta=delta))
    if resident_flag is not None:
        changes.extend(
            _relation_changes(
                graph,
                RESIDENT_ID,
                player_id,
                affinity_delta=affinity.get(RESIDENT_ID, 0),
                flags=[resident_flag],
            )
        )

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


def _relation_changes(
    graph: Graph,
    actor_id: str,
    player_id: str,
    *,
    affinity_delta: int = 0,
    flags: list[str] | None = None,
) -> list[GraphChange]:
    flags = flags or []
    if affinity_delta == 0 and not flags:
        return []

    edge_id, edge = _find_relation_edge(graph, actor_id, player_id)
    edge = graph.edges.get(edge_id)
    if edge is None:
        properties: dict[str, object] = {"affinity": affinity_delta}
        if flags:
            properties["flags"] = flags
        return [
            AddEdgeChange(
                type="add_edge",
                edge=GraphEdge(
                    id=edge_id,
                    type="relation",
                    from_node_id=actor_id,
                    to_node_id=player_id,
                    properties=properties,
                ),
            )
        ]

    changes: list[GraphChange] = []
    current = edge.properties.get("affinity")
    current_affinity = current if isinstance(current, int) else 0
    if affinity_delta != 0:
        changes.append(
            SetEdgePropertyChange(
                type="set_edge_property",
                edge_id=edge_id,
                path="affinity",
                value=current_affinity + affinity_delta,
            )
        )
    if flags:
        raw_flags = edge.properties.get("flags")
        next_flags = (
            [item for item in raw_flags if isinstance(item, str)]
            if isinstance(raw_flags, list)
            else []
        )
        for flag in flags:
            if flag not in next_flags:
                next_flags.append(flag)
        changes.append(
            SetEdgePropertyChange(
                type="set_edge_property",
                edge_id=edge_id,
                path="flags",
                value=next_flags,
            )
        )
    return changes


def _find_relation_edge(
    graph: Graph,
    actor_id: str,
    player_id: str,
) -> tuple[str, GraphEdge | None]:
    edge_id = _relation_edge_id(actor_id, player_id)
    edge = graph.edges.get(edge_id)
    if edge is not None:
        return edge_id, edge

    reverse_edge_id = _relation_edge_id(player_id, actor_id)
    reverse_edge = graph.edges.get(reverse_edge_id)
    if reverse_edge is not None:
        return reverse_edge_id, reverse_edge

    return edge_id, None


def _relation_edge_id(actor_id: str, player_id: str) -> str:
    return f"relation:{actor_id}:{player_id}"


def _mentions_reason(text: str) -> bool:
    return _has_any(
        text,
        (
            "이유",
            "사정",
            "왜",
            "무슨 일",
            "누락된 보급품",
            "보급품을 묻",
            "missing supplies",
            "reason",
            "why",
            "explain",
        ),
    )


def _mentions_report(text: str) -> bool:
    return _has_any(
        text,
        (
            "고발",
            "보고",
            "알립니다",
            "알린다",
            "훔쳤",
            "훔친",
            "stole",
            "stolen",
            "report",
            "accuse",
            "turn in",
        ),
    )


def _mentions_mediate(text: str) -> bool:
    return _has_any(
        text,
        (
            "설득",
            "봐 달",
            "용서",
            "중재",
            "사정",
            "mediate",
            "persuade",
            "forgive",
            "hear them out",
            "reason",
        ),
    )


def _mentions_quiet_return(text: str) -> bool:
    return _has_any(
        text,
        (
            "조용히",
            "몰래",
            "돌려놓",
            "반납",
            "quietly return",
            "quiet return",
            "return the supplies",
            "put back",
        ),
    )


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    normalized = text.casefold()
    return any(term.casefold() in normalized for term in terms)
