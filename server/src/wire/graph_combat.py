from src.game.runtime.state import GameRuntimeState
from src.wire.graph_payload_helpers import (
    node_name,
    optional_resource,
    require_node,
    resource,
)
from src.wire.models import (
    GraphCombatParticipantPayload,
    GraphCombatPayload,
    GraphHeartPayload,
)


def combat_payload(runtime: GameRuntimeState) -> GraphCombatPayload | None:
    state = runtime.progress.graph_combat_state
    if state is None:
        return None

    participants: list[GraphCombatParticipantPayload] = []
    for participant_id in state.participant_ids:
        node = require_node(runtime.graph, participant_id, "character")
        side = state.sides[participant_id]
        participants.append(
            GraphCombatParticipantPayload(
                id=node.id,
                name=node_name(node, runtime.content),
                side=side,
                hp=resource(node, "hp", "max_hp") if side == "player" else None,
                mp=optional_resource(node, "mp", "max_mp")
                if side == "player"
                else None,
            )
        )

    return GraphCombatPayload(
        round=state.round,
        outcome=state.outcome,
        player_hearts=GraphHeartPayload(current=state.player_hearts, maximum=3),
        enemy_hearts=GraphHeartPayload(current=state.enemy_hearts, maximum=3),
        active_enemy_id=state.active_enemy_id,
        participants=participants,
        last_roll=state.last_roll,
        last_dc=state.last_dc,
    )
