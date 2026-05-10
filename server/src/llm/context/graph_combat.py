from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.game.domain.combat import GraphCombatState
from src.game.domain.content import RuntimeContent, node_label
from src.game.domain.graph import Graph, GraphNode


HpState = Literal["healthy", "hurt", "critical", "downed"]
MpState = Literal["ready", "strained", "drained"]


class GraphCombatContextError(ValueError):
    pass


class GraphCombatParticipantView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    side: Literal["player", "enemy"]
    hp_state: HpState
    mp_state: MpState | None = None
    defeat_mode: str | None = None


class GraphCombatTraceView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    actor_id: str | None = None
    target_id: str | None = None
    state: str | None = None


class GraphCombatContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: str
    round: int = Field(ge=1, le=4)
    outcome: Literal["ongoing", "victory", "defeat", "fled"]
    participants: list[GraphCombatParticipantView]
    trace: list[GraphCombatTraceView]


def hp_state(current: int, maximum: int) -> HpState:
    if current <= 0:
        return "downed"
    if maximum <= 0:
        return "healthy"
    ratio = current / maximum
    if ratio <= 0.25:
        return "critical"
    if ratio <= 0.65:
        return "hurt"
    return "healthy"


def mp_state(current: int, maximum: int) -> MpState | None:
    if maximum <= 0:
        return None
    if current <= 0:
        return "drained"
    ratio = current / maximum
    if ratio <= 0.20:
        return "drained"
    if ratio <= 0.50:
        return "strained"
    return "ready"


def build_graph_combat_context(
    graph: Graph,
    state: GraphCombatState,
    content: RuntimeContent | None = None,
) -> GraphCombatContext:
    participants = [
        _participant_view(graph, state, participant_id, content)
        for participant_id in state.participant_ids
    ]
    return GraphCombatContext(
        location_id=state.location_id,
        round=state.round,
        outcome=state.outcome,
        participants=participants,
        trace=[
            GraphCombatTraceView(
                kind=event.kind,
                actor_id=event.actor_id,
                target_id=event.target_id,
                state=event.state,
            )
            for event in state.trace
        ],
    )


def _participant_view(
    graph: Graph,
    state: GraphCombatState,
    participant_id: str,
    content: RuntimeContent | None,
) -> GraphCombatParticipantView:
    node = _require_participant(graph, participant_id)
    side = state.sides.get(participant_id)
    if side is None:
        raise GraphCombatContextError(f"missing side for participant: {participant_id}")
    return GraphCombatParticipantView(
        id=participant_id,
        name=_name(node, content),
        side=side,
        hp_state=hp_state(
            _int_prop(node, "hp"),
            _int_prop(node, "max_hp"),
        ),
        mp_state=_node_mp_state(node),
        defeat_mode=_optional_str(node.properties.get("defeat_mode")),
    )


def _require_participant(graph: Graph, participant_id: str) -> GraphNode:
    node = graph.nodes.get(participant_id)
    if node is None:
        raise GraphCombatContextError(f"missing participant: {participant_id}")
    if node.type != "character":
        raise GraphCombatContextError(
            f"participant is not a character: {participant_id}"
        )
    return node


def _node_mp_state(node: GraphNode) -> MpState | None:
    current = node.properties.get("mp")
    maximum = node.properties.get("max_mp")
    if not isinstance(current, int) or not isinstance(maximum, int):
        return None
    return mp_state(current, maximum)


def _int_prop(node: GraphNode, key: str) -> int:
    value = node.properties.get(key)
    if not isinstance(value, int):
        raise GraphCombatContextError(f"missing numeric property {node.id}.{key}")
    return value


def _name(node: GraphNode, content: RuntimeContent | None) -> str:
    return node_label(content or RuntimeContent(), node)


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
