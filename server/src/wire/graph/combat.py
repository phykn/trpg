from src.game.runtime.state import GameRuntimeState
from src.game.domain.graph import GraphNode
from src.game.domain.graph.query import known_skills_of
from .values import (
    int_prop_default,
    node_name,
    optional_resource,
    optional_str,
    require_node,
    resource,
    static_value,
)
from src.wire.models import (
    GraphCombatParticipantPayload,
    GraphCombatPayload,
    GraphCombatSupportPayload,
    GraphHeartPayload,
)


_TACTIC_BY_ACTION = {
    "defend": "defend",
    "precise": "precise",
    "guarded": "guarded",
    "reckless": "reckless",
    "create_distance": "create_distance",
    "talk": "talk",
}


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
        available_supports=_available_supports(runtime),
        escape_ready=state.escape_ready,
        enemy_pressure=state.enemy_pressure,
        last_roll=state.last_roll,
        last_dc=state.last_dc,
    )


def _available_supports(runtime: GameRuntimeState) -> list[GraphCombatSupportPayload]:
    player = require_node(runtime.graph, runtime.progress.player_id, "character")
    current_mp = int_prop_default(player, "mp", 0)
    supports: list[GraphCombatSupportPayload] = []
    for edge in sorted(
        known_skills_of(runtime.graph, player.id),
        key=lambda candidate: candidate.to_node_id,
    ):
        skill = runtime.graph.nodes.get(edge.to_node_id)
        if skill is None or skill.type != "skill":
            continue
        tactic = _support_tactic(skill, runtime)
        if tactic is None:
            continue
        mp_cost = int_prop_default(skill, "mp_cost", 0)
        if current_mp < mp_cost:
            continue
        supports.append(
            GraphCombatSupportPayload(
                id=skill.id,
                kind="skill",
                name=node_name(skill, runtime.content),
                tactic=tactic,
                mp_cost=mp_cost,
            )
        )
    return supports


def _support_tactic(
    skill: GraphNode,
    runtime: GameRuntimeState,
) -> str | None:
    action = optional_str(static_value(skill, "action", runtime.content))
    tactic = _TACTIC_BY_ACTION.get(action or "")
    return tactic
