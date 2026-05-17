from pydantic import BaseModel, ConfigDict

from src.game.domain.action import Action
from src.game.domain.combat import GraphCombatAction, GraphCombatState
from src.game.domain.graph import Graph
from src.game.domain.graph.query import edges_from
from src.game.engines.graph.combat import (
    GraphCombatError,
    GraphCombatResult,
    plan_combat_exchange,
    plan_combat_start,
)
from src.game.engines.graph.growth import plan_xp_grant
from src.game.engines.graph.quest import (
    plan_quest_progress_for_character_death,
    plan_quest_rewards,
)
from src.llm.diag import engine_diag

from ..state import GameRuntimeState
from .apply import (
    GraphRuntimeApplyError,
    GraphRuntimeDirty,
    apply_runtime_graph_changes,
)


class GraphCombatDispatchError(ValueError):
    pass


class GraphCombatDispatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime: GameRuntimeState
    combat: GraphCombatResult
    outcome: str
    started: bool
    applied: int
    changed_node_ids: list[str]
    changed_edge_ids: list[str]
    removed_edge_ids: list[str]


def dispatch_graph_combat_action(
    runtime: GameRuntimeState,
    action: Action,
) -> GraphCombatDispatchResult:
    engine_diag("combat:start", action=action.verb)
    try:
        state, started = _resolve_state(runtime, action)
        if started:
            combat_result = GraphCombatResult(changes=[], state=state)
        else:
            combat_action = _combat_action_from_action(
                runtime.graph,
                action,
                player_id=state.player_id,
                in_combat=True,
            )
            combat_result = plan_combat_exchange(
                runtime.graph,
                state,
                runtime.progress.player_id,
                combat_action,
            )
        applied = apply_runtime_graph_changes(runtime, combat_result.changes)
    except (GraphCombatError, GraphRuntimeApplyError) as exc:
        engine_diag("combat:fail", action=action.verb, err=type(exc).__name__)
        raise GraphCombatDispatchError(str(exc)) from exc

    graph_runtime = applied.runtime
    applied_count = applied.applied
    dirty = GraphRuntimeDirty.from_apply_result(applied)
    completed_quest_ids: list[str] = []
    if combat_result.state.outcome == "victory":
        for target_id in _victory_target_ids(combat_result.state):
            reward_xp = _xp_reward(graph_runtime.graph, target_id)
            if reward_xp > 0:
                xp_apply = apply_runtime_graph_changes(
                    graph_runtime,
                    plan_xp_grant(
                        graph_runtime.graph,
                        graph_runtime.progress.player_id,
                        reward_xp,
                    ).changes,
                )
                graph_runtime = xp_apply.runtime
                applied_count += xp_apply.applied
                dirty.add_apply_result(xp_apply)
            quest_progress = plan_quest_progress_for_character_death(
                graph_runtime.graph,
                target_id,
            )
            if quest_progress.changes:
                progress_apply = apply_runtime_graph_changes(
                    graph_runtime,
                    quest_progress.changes,
                )
                graph_runtime = progress_apply.runtime
                applied_count += progress_apply.applied
                dirty.add_apply_result(progress_apply)
                completed_quest_ids.extend(quest_progress.completed_quest_ids)
        for quest_id in completed_quest_ids:
            reward = plan_quest_rewards(
                graph_runtime.graph,
                quest_id,
                graph_runtime.progress.player_id,
            )
            if reward.changes:
                reward_apply = apply_runtime_graph_changes(
                    graph_runtime,
                    reward.changes,
                )
                graph_runtime = reward_apply.runtime
                applied_count += reward_apply.applied
                dirty.add_apply_result(reward_apply)

    progress_update = {
        "graph_combat_state": (
            combat_result.state if combat_result.state.outcome == "ongoing" else None
        )
    }
    if graph_runtime.progress.active_quest_id in completed_quest_ids:
        progress_update["active_quest_id"] = None
    next_progress = graph_runtime.progress.model_copy(update=progress_update)
    next_runtime = graph_runtime.model_copy(update={"progress": next_progress})
    engine_diag(
        "combat:end",
        started=started,
        outcome=combat_result.state.outcome,
        applied=applied_count,
    )
    return GraphCombatDispatchResult(
        runtime=next_runtime,
        combat=combat_result,
        outcome=combat_result.state.outcome,
        started=started,
        applied=applied_count,
        changed_node_ids=sorted(dirty.changed_node_ids),
        changed_edge_ids=sorted(dirty.changed_edge_ids),
        removed_edge_ids=sorted(dirty.removed_edge_ids),
    )


def _victory_target_ids(state: GraphCombatState) -> list[str]:
    target_ids: list[str] = []
    for event in state.trace:
        if event.target_id is None or event.target_id not in state.enemy_ids:
            continue
        if event.kind in {"enemy_defeated", "forced_end"}:
            target_ids.append(event.target_id)
    return target_ids


def _xp_reward(graph: Graph, character_id: str) -> int:
    node = graph.nodes.get(character_id)
    if node is None:
        return 0
    value = node.properties.get("xp_reward")
    return value if isinstance(value, int) and value > 0 else 0


def _resolve_state(
    runtime: GameRuntimeState,
    action: Action,
) -> tuple[GraphCombatState, bool]:
    state = runtime.progress.graph_combat_state
    if state is not None:
        return state, False

    if action.verb != "attack":
        raise GraphCombatDispatchError(f"cannot start graph combat with {action.verb}")

    target_id = _target_id_for_start(action)
    try:
        result = plan_combat_start(runtime.graph, runtime.progress.player_id, target_id)
    except GraphCombatError as exc:
        raise GraphCombatDispatchError(str(exc)) from exc
    return result.state, True


def _combat_action_from_action(
    graph: Graph,
    action: Action,
    *,
    player_id: str,
    in_combat: bool,
) -> GraphCombatAction:
    if action.verb == "attack":
        tactic = _attack_tactic(action.how)
        support_id = _single(action.with_)
        if support_id is None and action.how == "auto":
            support_id = _auto_skill_support_id(graph, player_id, tactic)
        support_kind = _support_kind(graph, support_id)
        return GraphCombatAction(
            kind=tactic,
            target_id=_single(action.what),
            support_id=support_id if support_kind else None,
            support_kind=support_kind,
        )
    if (
        in_combat
        and action.verb == "move"
        and action.how in ("flee", "hasty", "create_distance")
    ):
        support_id = _single(action.with_)
        support_kind = _support_kind(graph, support_id)
        return GraphCombatAction(
            kind="create_distance",
            support_id=support_id if support_kind else None,
            support_kind=support_kind,
        )
    if in_combat and action.verb == "speak":
        support_id = _single(action.with_)
        support_kind = _support_kind(graph, support_id)
        return GraphCombatAction(
            kind="talk",
            target_id=_single(action.to) or _single(action.what),
            support_id=support_id if support_kind else None,
            support_kind=support_kind,
        )
    if in_combat and action.verb == "pass":
        support_id = _single(action.with_)
        support_kind = _support_kind(graph, support_id)
        return GraphCombatAction(
            kind="guarded",
            support_id=support_id if support_kind else None,
            support_kind=support_kind,
        )
    raise GraphCombatDispatchError(f"unsupported graph combat action: {action.verb}")


def _support_kind(graph: Graph, node_id: str | None) -> str | None:
    if node_id is None:
        return None
    node = graph.nodes.get(node_id)
    if node is None:
        raise GraphCombatDispatchError(f"missing combat support: {node_id}")
    if node.type == "skill":
        return "skill"
    if node.type == "item" and (
        "support_action" in node.properties or "action" in node.properties
    ):
        return "item"
    raise GraphCombatDispatchError(f"unsupported combat support: {node_id}")


def _auto_skill_support_id(
    graph: Graph, player_id: str, action_kind: str
) -> str | None:
    player = graph.nodes.get(player_id)
    if player is None:
        return None
    current_mp = _int_value(player.properties.get("mp"), default=0)
    for edge in edges_from(graph, player_id, "knows_skill"):
        skill = graph.nodes.get(edge.to_node_id)
        if skill is None or skill.type != "skill":
            continue
        supported_action = _string_prop(
            skill,
            "action",
            fallback=_string_prop(
                skill,
                "kind",
                fallback=_string_prop(skill, "type"),
            ),
        )
        mp_cost = _int_value(skill.properties.get("mp_cost"), default=0)
        if _supports_action(supported_action, action_kind) and current_mp >= mp_cost:
            return skill.id
    return None


def _attack_tactic(how: str | None) -> str:
    if how == "reckless":
        return "reckless"
    if how == "guarded":
        return "guarded"
    return "precise"


def _supports_action(supported_action: str | None, action_kind: str) -> bool:
    if supported_action == action_kind:
        return True
    legacy = {
        "attack": {"precise", "reckless"},
        "defend": {"guarded"},
        "flee": {"create_distance"},
        "social": {"talk"},
    }
    return action_kind in legacy.get(supported_action or "", set())


def _target_id_for_start(action: Action) -> str:
    if action.verb == "attack":
        target_id = _single(action.what)
    else:
        target_id = None
    if target_id is None:
        raise GraphCombatDispatchError("graph combat target is required")
    return target_id


def _single(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value and isinstance(value[0], str):
        return value[0]
    return None


def _string_prop(node: object, key: str, *, fallback: str | None = None) -> str | None:
    properties = getattr(node, "properties", None)
    if not isinstance(properties, dict):
        return fallback
    value = properties.get(key)
    return value if isinstance(value, str) and value else fallback


def _int_value(value: object, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    return default
