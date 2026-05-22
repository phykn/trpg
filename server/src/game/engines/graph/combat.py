from random import randint

from pydantic import BaseModel, ConfigDict

from src.game.domain.combat import (
    CombatActionKind,
    CombatSupportKind,
    GraphCombatAction,
    GraphCombatState,
    GraphCombatTraceEvent,
)
from src.game.domain.graph import (
    Graph,
    GraphChange,
    GraphNode,
    RemoveEdgeChange,
    SetNodePropertyChange,
)
from src.game.domain.graph.query import edges_from, known_skills_of, location_of
from src.game.rules import RULES


class GraphCombatError(ValueError):
    pass


class GraphCombatResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changes: list[GraphChange]
    state: GraphCombatState


class _SupportPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    support_id: str
    support_kind: CombatSupportKind
    bonus: int
    mp_cost: int = 0
    consume_edge_id: str | None = None
    effect: str | None = None


def plan_combat_start(
    graph: Graph,
    player_id: str,
    enemy_id: str,
) -> GraphCombatResult:
    player = _require_character(graph, player_id)
    enemy = _require_character(graph, enemy_id)
    if player_id == enemy_id:
        raise GraphCombatError("combat requires different characters")
    _require_player_can_fight(player)
    _require_combatant_can_fight(enemy)

    player_location = location_of(graph, player_id)
    enemy_location = location_of(graph, enemy_id)
    if player_location is None:
        raise GraphCombatError(f"missing location: {player_id}")
    if player_location != enemy_location:
        raise GraphCombatError("combatants must share the same location")

    state = GraphCombatState(
        location_id=player_location,
        player_id=player_id,
        active_enemy_id=enemy_id,
        enemy_ids=[enemy_id],
        participant_ids=[player_id, enemy_id],
        sides={player_id: "player", enemy_id: "enemy"},
        player_hearts=RULES.combat.starting_hearts,
        enemy_hearts=RULES.combat.starting_hearts,
        trace=[
            GraphCombatTraceEvent(
                kind="combat_started",
                actor_id=player_id,
                target=enemy_id,
            )
        ],
    )
    return GraphCombatResult(changes=[], state=state)


def plan_combat_exchange(
    graph: Graph,
    state: GraphCombatState,
    actor_id: str,
    action: GraphCombatAction,
    *,
    dice: int | None = None,
) -> GraphCombatResult:
    if state.outcome != "ongoing":
        raise GraphCombatError(f"combat is already resolved: {state.outcome}")
    if actor_id != state.player_id:
        raise GraphCombatError("only the player actor can drive this combat slice")

    player = _require_character(graph, state.player_id)
    _require_player_can_fight(player)
    target = action.target or state.active_enemy_id
    enemy = _require_enemy(graph, state, target)
    _require_combatant_can_fight(enemy)

    support = _resolve_support(graph, player, action)
    changes = _resource_changes(player, support)
    roll = _normalize_roll(dice)
    dc = _combat_dc(player, enemy, action.kind, support)
    success = roll >= dc

    next_state = state.model_copy(deep=True)
    next_state.active_enemy_id = enemy.id
    next_state.last_action = action.kind
    next_state.last_support_id = action.support_id
    next_state.last_support_kind = action.support_kind
    next_state.last_roll = roll
    next_state.last_dc = dc

    _apply_heart_result(next_state, actor_id, enemy.id, action.kind, success, support)
    _apply_terminal_result(changes, graph, next_state, player, enemy)

    if next_state.outcome == "ongoing":
        next_state.round = state.round + 1

    return GraphCombatResult(changes=changes, state=next_state)


def _resolve_support(
    graph: Graph,
    player: GraphNode,
    action: GraphCombatAction,
) -> _SupportPlan | None:
    if action.support_id is None and action.support_kind is None:
        return None
    if action.support_id is None or action.support_kind is None:
        raise GraphCombatError("support_id and support_kind must be provided together")
    if action.support_kind == "skill":
        return _resolve_skill_support(graph, player, action)
    return _resolve_item_support(graph, player, action)


def _resolve_skill_support(
    graph: Graph,
    player: GraphNode,
    action: GraphCombatAction,
) -> _SupportPlan:
    assert action.support_id is not None
    skill = graph.nodes.get(action.support_id)
    if skill is None:
        raise GraphCombatError(f"missing skill: {action.support_id}")
    if skill.type != "skill":
        raise GraphCombatError(f"node is not a skill: {action.support_id}")
    if not any(
        edge.to_node_id == action.support_id
        for edge in known_skills_of(graph, player.id)
    ):
        raise GraphCombatError(f"{player.id} does not know skill: {action.support_id}")

    supported_action = _string_prop(skill, "action")
    if not _supports_action(supported_action, action.kind):
        raise GraphCombatError(f"skill does not support action: {action.support_id}")

    mp_cost = _int_value(skill.properties.get("mp_cost"), default=0)
    current_mp = _int_prop(player, "mp")
    if current_mp < mp_cost:
        raise GraphCombatError(f"not enough mp: {current_mp} < {mp_cost}")

    return _SupportPlan(
        support_id=action.support_id,
        support_kind="skill",
        bonus=_bounded_bonus(skill.properties.get("bonus")),
        mp_cost=mp_cost,
    )


def _resolve_item_support(
    graph: Graph,
    player: GraphNode,
    action: GraphCombatAction,
) -> _SupportPlan:
    assert action.support_id is not None
    item = graph.nodes.get(action.support_id)
    if item is None:
        raise GraphCombatError(f"missing item: {action.support_id}")
    if item.type != "item":
        raise GraphCombatError(f"node is not an item: {action.support_id}")

    placement_edge = next(
        (
            edge
            for edge in edges_from(graph, player.id)
            if edge.to_node_id == action.support_id
            and edge.type in {"carries", "equips"}
        ),
        None,
    )
    if placement_edge is None:
        raise GraphCombatError(f"{player.id} does not have item: {action.support_id}")

    supported_action = _string_prop(item, "action")
    if not _supports_action(supported_action, action.kind):
        raise GraphCombatError(f"item does not support action: {action.support_id}")

    return _SupportPlan(
        support_id=action.support_id,
        support_kind="item",
        bonus=_bounded_bonus(item.properties.get("bonus")),
        consume_edge_id=placement_edge.id
        if item.properties.get("consumable") is True
        else None,
        effect=_string_prop(item, "effect"),
    )


def _resource_changes(
    player: GraphNode,
    support: _SupportPlan | None,
) -> list[GraphChange]:
    if support is None:
        return []

    changes: list[GraphChange] = []
    if support.mp_cost > 0:
        changes.append(_set(player.id, "mp", _int_prop(player, "mp") - support.mp_cost))
    if support.consume_edge_id is not None:
        changes.append(
            RemoveEdgeChange(
                type="remove_edge",
                edge_id=support.consume_edge_id,
            )
        )
    return changes


def _combat_dc(
    player: GraphNode,
    enemy: GraphNode,
    action: CombatActionKind,
    support: _SupportPlan | None,
) -> int:
    raw_dc = RULES.combat.base_dc + _level(enemy) - _level(player)
    if support is not None and support.support_kind == "skill":
        raw_dc -= support.bonus
    elif support is not None and support.effect == "dc_down":
        raw_dc -= support.bonus
    elif support is not None and support.effect == "dc_up":
        raw_dc += support.bonus
    return min(RULES.combat.max_dc, max(RULES.combat.min_dc, raw_dc))


def _apply_heart_result(
    state: GraphCombatState,
    actor_id: str,
    enemy_id: str,
    kind: CombatActionKind,
    success: bool,
    support: _SupportPlan | None,
) -> None:
    if success:
        if kind == "attack":
            state.enemy_hearts = max(0, state.enemy_hearts - 1)
            target = enemy_id
        elif kind == "defend":
            state.player_hearts = min(
                RULES.combat.starting_hearts,
                state.player_hearts + 1,
            )
            target = actor_id
        elif kind == "talk":
            state.enemy_pressure += 1
            target = enemy_id
            if state.enemy_pressure >= 2 or state.enemy_hearts <= 1:
                state.outcome = "combat_stopped"
                state.trace.append(
                    GraphCombatTraceEvent(
                        kind="combat_stopped",
                        actor_id=actor_id,
                        target=enemy_id,
                        state=_heart_state(state),
                    )
                )
                return
        elif kind == "flee":
            target = actor_id
            state.escape_ready = True
            state.outcome = "escaped"
        else:
            raise GraphCombatError(f"unsupported combat action: {kind}")
        state.trace.append(
            GraphCombatTraceEvent(
                kind=f"player_{kind}_success",
                actor_id=actor_id,
                target=target,
                state=_heart_state(state),
            )
        )
        return

    state.player_hearts = max(0, state.player_hearts - 1)
    state.trace.append(
        GraphCombatTraceEvent(
            kind=f"player_{kind}_failure",
            actor_id=actor_id,
            target=enemy_id if kind in {"attack", "talk"} else actor_id,
            state=_heart_state(state),
        )
    )


def _apply_terminal_result(
    changes: list[GraphChange],
    graph: Graph,
    state: GraphCombatState,
    player: GraphNode,
    enemy: GraphNode,
) -> None:
    if state.outcome in {"escaped", "combat_stopped"}:
        return
    if state.enemy_hearts <= 0:
        _plan_defeat(
            changes,
            enemy,
            mode="dead",
            marker="dead",
            set_alive_false=True,
        )
        state.outcome = "victory"
        state.trace.append(
            GraphCombatTraceEvent(
                kind="enemy_defeated",
                actor_id=state.player_id,
                target=enemy.id,
                state="hearts:0",
            )
        )
        return
    if state.player_hearts <= 0:
        hp_loss = max(0, state.enemy_hearts)
        current_hp = _int_prop(player, "hp")
        changes.append(_set(player.id, "hp", max(0, current_hp - hp_loss)))
        state.outcome = "defeat"
        state.trace.append(
            GraphCombatTraceEvent(
                kind="player_defeated",
                actor_id=enemy.id,
                target=player.id,
                state=f"hp_loss:{hp_loss}",
            )
        )


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
    target: str,
) -> GraphNode:
    if target not in state.enemy_ids:
        raise GraphCombatError(f"target is not an enemy in this combat: {target}")
    return _require_character(graph, target)


def _require_combatant_can_fight(node: GraphNode) -> None:
    if node.properties.get("alive") is False:
        raise GraphCombatError(f"character cannot fight: {node.id}")
    status = node.properties.get("status", [])
    if isinstance(status, list) and "dead" in status:
        raise GraphCombatError(f"character cannot fight: {node.id}")


def _require_player_can_fight(node: GraphNode) -> None:
    _require_combatant_can_fight(node)
    hp = _int_prop(node, "hp")
    max_hp = _int_prop(node, "max_hp")
    if hp <= 0 or max_hp <= 0:
        raise GraphCombatError(f"character cannot fight: {node.id}")


def _plan_defeat(
    changes: list[GraphChange],
    node: GraphNode,
    *,
    mode: str,
    marker: str,
    set_alive_false: bool,
) -> None:
    if set_alive_false:
        changes.append(_set(node.id, "alive", False))
    changes.append(_set(node.id, "defeat_mode", mode))
    status = node.properties.get("status", [])
    next_status = list(status) if isinstance(status, list) else []
    if marker not in next_status:
        next_status.append(marker)
    changes.append(_set(node.id, "status", next_status))


def _normalize_roll(dice: int | None) -> int:
    roll = randint(1, 20) if dice is None else dice
    if roll < 1 or roll > 20:
        raise GraphCombatError(f"dice roll must be between 1 and 20: {roll}")
    return roll


def _heart_state(state: GraphCombatState) -> str:
    return f"player:{state.player_hearts},enemy:{state.enemy_hearts},dc:{state.last_dc},roll:{state.last_roll}"


def _level(node: GraphNode) -> int:
    return _int_value(node.properties.get("level"), default=1)


def _bounded_bonus(value: object) -> int:
    bonus = _int_value(value, default=0)
    return min(4, max(0, bonus))


def _supports_action(
    supported_action: str | None, action_kind: CombatActionKind
) -> bool:
    return supported_action == action_kind


def _string_prop(
    node: GraphNode,
    key: str,
    *,
    fallback: str | None = None,
) -> str | None:
    value = node.properties.get(key)
    return value if isinstance(value, str) else fallback


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
