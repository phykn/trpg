from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.game.domain.combat import GraphCombatState
from src.game.domain.content import RuntimeContent, node_label
from src.game.domain.graph import Graph, GraphNode
from src.game.domain.resource_state import HpState, MpState, hp_state, mp_state


class GraphCombatContextError(ValueError):
    pass


class GraphCombatParticipantView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    side: Literal["player", "enemy"]
    hp_state: HpState | None = None
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
    round: int = Field(ge=1)
    player_hearts: int = Field(ge=0, le=3)
    enemy_hearts: int = Field(ge=0, le=3)
    escape_ready: bool = False
    enemy_pressure: int = Field(default=0, ge=0)
    outcome: Literal["ongoing", "victory", "defeat", "fled"]
    participants: list[GraphCombatParticipantView]
    trace: list[GraphCombatTraceView]


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
        player_hearts=state.player_hearts,
        enemy_hearts=state.enemy_hearts,
        escape_ready=state.escape_ready,
        enemy_pressure=state.enemy_pressure,
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
        hp_state=_node_hp_state(node) if side == "player" else None,
        mp_state=_node_mp_state(node) if side == "player" else None,
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


def _node_hp_state(node: GraphNode) -> HpState | None:
    current = node.properties.get("hp")
    maximum = node.properties.get("max_hp")
    if not isinstance(current, int) or not isinstance(maximum, int):
        return None
    return hp_state(current, maximum)


def _int_prop(node: GraphNode, key: str) -> int:
    value = node.properties.get(key)
    if not isinstance(value, int):
        raise GraphCombatContextError(f"missing numeric property {node.id}.{key}")
    return value


def _name(node: GraphNode, content: RuntimeContent | None) -> str:
    return node_label(content or RuntimeContent(), node)


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
