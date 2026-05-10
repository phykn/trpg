from pydantic import BaseModel, ConfigDict

from src.game.domain.action import Action
from src.game.domain.combat import GraphCombatAction, GraphCombatState
from src.game.domain.graph import Graph
from src.game.engines.graph_combat import (
    GraphCombatError,
    GraphCombatResult,
    plan_combat_exchange,
    plan_combat_start,
)
from src.game.engines.graph_quest import (
    plan_quest_progress_for_character_defeat,
    plan_quest_rewards,
)
from src.llm.diag import engine_diag

from .apply import GraphRuntimeApplyError, apply_runtime_graph_changes
from .state import GameRuntimeState


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
        combat_action = _combat_action_from_action(
            runtime.graph,
            action,
            in_combat=not started,
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
    changed_node_ids = set(applied.changed_node_ids)
    changed_edge_ids = set(applied.changed_edge_ids)
    removed_edge_ids = set(applied.removed_edge_ids)
    completed_quest_ids: list[str] = []
    if combat_result.state.outcome == "victory":
        for target_id in _victory_target_ids(combat_result.state):
            quest_progress = plan_quest_progress_for_character_defeat(
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
                changed_node_ids.update(progress_apply.changed_node_ids)
                changed_edge_ids.update(progress_apply.changed_edge_ids)
                removed_edge_ids.update(progress_apply.removed_edge_ids)
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
                changed_node_ids.update(reward_apply.changed_node_ids)
                changed_edge_ids.update(reward_apply.changed_edge_ids)
                removed_edge_ids.update(reward_apply.removed_edge_ids)

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
        changed_node_ids=sorted(changed_node_ids),
        changed_edge_ids=sorted(changed_edge_ids),
        removed_edge_ids=sorted(removed_edge_ids),
    )


def _victory_target_ids(state: GraphCombatState) -> list[str]:
    target_ids: list[str] = []
    for event in state.trace:
        if event.target_id is None or event.target_id not in state.enemy_ids:
            continue
        if event.kind in {"enemy_defeated", "forced_end"}:
            target_ids.append(event.target_id)
    return target_ids


def _resolve_state(
    runtime: GameRuntimeState,
    action: Action,
) -> tuple[GraphCombatState, bool]:
    state = runtime.progress.graph_combat_state
    if state is not None:
        return state, False

    if action.verb not in ("attack", "cast"):
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
    in_combat: bool,
) -> GraphCombatAction:
    if action.verb == "attack":
        skill_id = _skill_id_or_none(graph, _single(action.with_))
        return GraphCombatAction(
            kind="cast" if skill_id else "attack",
            target_id=_single(action.what),
            skill_id=skill_id,
        )
    if action.verb == "cast":
        return GraphCombatAction(
            kind="cast",
            target_id=_single(action.to),
            skill_id=_single(action.with_) or _single(action.what),
        )
    if in_combat and action.verb == "move" and action.how in ("flee", "hasty"):
        return GraphCombatAction(kind="flee")
    if in_combat and action.verb == "pass":
        return GraphCombatAction(kind="defend")
    raise GraphCombatDispatchError(f"unsupported graph combat action: {action.verb}")


def _skill_id_or_none(graph: Graph, node_id: str | None) -> str | None:
    if node_id is None:
        return None
    node = graph.nodes.get(node_id)
    if node is None or node.type != "skill":
        return None
    return node_id


def _target_id_for_start(action: Action) -> str:
    if action.verb == "attack":
        target_id = _single(action.what)
    elif action.verb == "cast":
        target_id = _single(action.to)
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
