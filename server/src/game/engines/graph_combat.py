from math import ceil
from pydantic import BaseModel, ConfigDict

from src.game.domain.combat import (
    GraphCombatAction,
    GraphCombatState,
    GraphCombatTraceEvent,
)
from src.game.domain.graph import Graph, GraphChange, GraphNode, SetNodePropertyChange
from src.game.domain.graph_query import edges_from, location_of


class GraphCombatError(ValueError):
    pass


class GraphCombatResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changes: list[GraphChange]
    state: GraphCombatState


def plan_combat_start(
    graph: Graph,
    player_id: str,
    enemy_id: str,
) -> GraphCombatResult:
    player = _require_character(graph, player_id)
    enemy = _require_character(graph, enemy_id)
    if player_id == enemy_id:
        raise GraphCombatError("combat requires different characters")
    _require_can_fight(player)
    _require_can_fight(enemy)

    player_location = location_of(graph, player_id)
    enemy_location = location_of(graph, enemy_id)
    if player_location is None:
        raise GraphCombatError(f"missing location: {player_id}")
    if player_location != enemy_location:
        raise GraphCombatError("combatants must share the same location")

    state = GraphCombatState(
        location_id=player_location,
        player_id=player_id,
        enemy_ids=[enemy_id],
        participant_ids=[player_id, enemy_id],
        sides={player_id: "player", enemy_id: "enemy"},
        trace=[
            GraphCombatTraceEvent(
                kind="combat_started",
                actor_id=player_id,
                target_id=enemy_id,
            )
        ],
    )
    return GraphCombatResult(changes=[], state=state)


def plan_combat_exchange(
    graph: Graph,
    state: GraphCombatState,
    actor_id: str,
    action: GraphCombatAction,
) -> GraphCombatResult:
    if state.outcome != "ongoing":
        raise GraphCombatError(f"combat is already resolved: {state.outcome}")
    if actor_id != state.player_id:
        raise GraphCombatError("only the player actor can drive this combat slice")

    player = _require_character(graph, state.player_id)
    _require_can_fight(player)
    target_id = action.target_id or _first_live_enemy_id(graph, state)
    enemy = _require_enemy(graph, state, target_id)
    _require_can_fight(enemy)

    changes: list[GraphChange] = []
    next_state = state.model_copy(deep=True)
    next_state.last_action = action.kind

    if action.kind == "flee":
        next_state.outcome = "fled"
        next_state.trace.append(
            GraphCombatTraceEvent(kind="player_fled", actor_id=actor_id)
        )
        return GraphCombatResult(changes=[], state=next_state)

    player_hp = _int_prop(player, "hp")
    player_max_hp = _int_prop(player, "max_hp")
    enemy_hp = _int_prop(enemy, "hp")
    enemy_max_hp = _int_prop(enemy, "max_hp")

    enemy_hp_after = enemy_hp
    player_hp_after = player_hp

    if action.kind == "attack":
        amount = _attack_amount(player, enemy_max_hp)
        enemy_hp_after = _plan_hp_loss(changes, enemy.id, enemy_hp, amount)
        next_state.trace.append(
            GraphCombatTraceEvent(
                kind="player_attacked",
                actor_id=actor_id,
                target_id=enemy.id,
                state=_hp_state(enemy_hp_after, enemy_max_hp),
            )
        )
    elif action.kind == "cast":
        amount = _plan_cast(changes, graph, player, enemy, action)
        enemy_hp_after = _plan_hp_loss(changes, enemy.id, enemy_hp, amount)
        next_state.trace.append(
            GraphCombatTraceEvent(
                kind="player_cast",
                actor_id=actor_id,
                target_id=enemy.id,
                state=_hp_state(enemy_hp_after, enemy_max_hp),
            )
        )
    elif action.kind == "defend":
        next_state.trace.append(
            GraphCombatTraceEvent(kind="player_defended", actor_id=actor_id)
        )

    if enemy_hp_after <= 0:
        _plan_defeat(
            changes,
            enemy,
            mode="unconscious",
            marker="defeated",
            set_hp_zero=False,
        )
        next_state.outcome = "victory"
        next_state.trace.append(
            GraphCombatTraceEvent(
                kind="enemy_defeated",
                actor_id=actor_id,
                target_id=enemy.id,
                state="downed",
            )
        )
        return GraphCombatResult(changes=changes, state=next_state)

    if state.round >= 4:
        _force_terminal_outcome(
            changes,
            next_state,
            player=player,
            enemy=enemy,
            player_hp=player_hp_after,
            enemy_hp=enemy_hp_after,
        )
        return GraphCombatResult(changes=changes, state=next_state)

    incoming = _enemy_response_amount(player_max_hp, defended=action.kind == "defend")
    player_hp_after = _plan_hp_loss(changes, player.id, player_hp, incoming)
    next_state.trace.append(
        GraphCombatTraceEvent(
            kind="enemy_pressed",
            actor_id=enemy.id,
            target_id=player.id,
            state=_hp_state(player_hp_after, player_max_hp),
        )
    )
    if player_hp_after <= 0:
        _plan_defeat(
            changes,
            player,
            mode="downed",
            marker="downed",
            set_hp_zero=False,
        )
        next_state.outcome = "defeat"
        next_state.trace.append(
            GraphCombatTraceEvent(
                kind="player_downed",
                actor_id=enemy.id,
                target_id=player.id,
                state="downed",
            )
        )
        return GraphCombatResult(changes=changes, state=next_state)

    next_state.round = min(4, state.round + 1)
    return GraphCombatResult(changes=changes, state=next_state)


def _require_character(graph: Graph, character_id: str) -> GraphNode:
    node = graph.nodes.get(character_id)
    if node is None:
        raise GraphCombatError(f"missing character: {character_id}")
    if node.type != "character":
        raise GraphCombatError(f"node is not a character: {character_id}")
    return node


def _require_enemy(
    graph: Graph,
    state: GraphCombatState,
    target_id: str,
) -> GraphNode:
    if target_id not in state.enemy_ids:
        raise GraphCombatError(f"target is not an enemy in this combat: {target_id}")
    return _require_character(graph, target_id)


def _require_can_fight(node: GraphNode) -> None:
    if node.properties.get("alive") is False:
        raise GraphCombatError(f"character cannot fight: {node.id}")
    hp = _int_prop(node, "hp")
    max_hp = _int_prop(node, "max_hp")
    if hp <= 0 or max_hp <= 0:
        raise GraphCombatError(f"character cannot fight: {node.id}")


def _first_live_enemy_id(graph: Graph, state: GraphCombatState) -> str:
    for enemy_id in state.enemy_ids:
        enemy = _require_character(graph, enemy_id)
        if enemy.properties.get("alive") is not False and _int_prop(enemy, "hp") > 0:
            return enemy_id
    raise GraphCombatError("combat has no live enemy")


def _plan_cast(
    changes: list[GraphChange],
    graph: Graph,
    player: GraphNode,
    enemy: GraphNode,
    action: GraphCombatAction,
) -> int:
    if action.skill_id is None:
        raise GraphCombatError("skill_id is required for cast")
    skill = graph.nodes.get(action.skill_id)
    if skill is None:
        raise GraphCombatError(f"missing skill: {action.skill_id}")
    if skill.type != "skill":
        raise GraphCombatError(f"node is not a skill: {action.skill_id}")
    if not any(
        edge.to_node_id == action.skill_id
        for edge in edges_from(graph, player.id, "knows_skill")
    ):
        raise GraphCombatError(f"{player.id} does not know skill: {action.skill_id}")

    kind = skill.properties.get("kind", skill.properties.get("type"))
    if kind != "attack":
        raise GraphCombatError(f"skill is not a combat attack: {action.skill_id}")

    mp_cost = _int_value(skill.properties.get("mp_cost"), default=0)
    current_mp = _int_prop(player, "mp")
    if current_mp < mp_cost:
        raise GraphCombatError(f"not enough mp: {current_mp} < {mp_cost}")
    if mp_cost:
        changes.append(_set(player.id, "mp", current_mp - mp_cost))

    power = _int_value(skill.properties.get("power"), default=0)
    if power > 0:
        return power
    return max(1, ceil(_int_prop(enemy, "max_hp") * 0.55))


def _attack_amount(player: GraphNode, enemy_max_hp: int) -> int:
    stat = _stat_value(player, preferred="body", default=2)
    return max(1, ceil(enemy_max_hp * 0.38) + max(0, stat - 2))


def _enemy_response_amount(player_max_hp: int, *, defended: bool) -> int:
    ratio = 0.10 if defended else 0.25
    return max(1, ceil(player_max_hp * ratio))


def _force_terminal_outcome(
    changes: list[GraphChange],
    state: GraphCombatState,
    *,
    player: GraphNode,
    enemy: GraphNode,
    player_hp: int,
    enemy_hp: int,
) -> None:
    player_ratio = player_hp / max(1, _int_prop(player, "max_hp"))
    enemy_ratio = enemy_hp / max(1, _int_prop(enemy, "max_hp"))
    if player_ratio >= enemy_ratio:
        _plan_defeat(
            changes,
            enemy,
            mode="escaped",
            marker="defeated",
            set_hp_zero=False,
        )
        state.outcome = "victory"
        target_id = enemy.id
    else:
        _plan_defeat(
            changes,
            player,
            mode="downed",
            marker="downed",
            set_hp_zero=True,
        )
        state.outcome = "defeat"
        target_id = player.id
    state.trace.append(
        GraphCombatTraceEvent(
            kind="forced_end",
            actor_id=state.player_id,
            target_id=target_id,
        )
    )


def _plan_hp_loss(
    changes: list[GraphChange],
    node_id: str,
    current_hp: int,
    amount: int,
) -> int:
    next_hp = max(0, current_hp - amount)
    changes.append(_set(node_id, "hp", next_hp))
    return next_hp


def _plan_defeat(
    changes: list[GraphChange],
    node: GraphNode,
    *,
    mode: str,
    marker: str,
    set_hp_zero: bool,
) -> None:
    if set_hp_zero:
        changes.append(_set(node.id, "hp", 0))
    changes.append(_set(node.id, "defeat_mode", mode))
    status = node.properties.get("status", [])
    next_status = list(status) if isinstance(status, list) else []
    if marker not in next_status:
        next_status.append(marker)
    changes.append(_set(node.id, "status", next_status))


def _hp_state(hp: int, max_hp: int) -> str:
    if hp <= 0:
        return "downed"
    ratio = hp / max(1, max_hp)
    if ratio <= 0.25:
        return "critical"
    if ratio <= 0.65:
        return "hurt"
    return "healthy"


def _stat_value(
    node: GraphNode,
    *,
    preferred: str,
    default: int,
) -> int:
    stats = node.properties.get("stats")
    if not isinstance(stats, dict):
        return default
    value = stats.get(preferred, default)
    return value if isinstance(value, int) else default


def _int_prop(node: GraphNode, key: str) -> int:
    value = node.properties.get(key)
    if not isinstance(value, int):
        raise GraphCombatError(f"missing numeric property {node.id}.{key}")
    return value


def _int_value(value: object, *, default: int) -> int:
    return value if isinstance(value, int) else default


def _set(node_id: str, path: str, value: object) -> SetNodePropertyChange:
    return SetNodePropertyChange(
        type="set_node_property",
        node_id=node_id,
        path=path,
        value=value,
    )
