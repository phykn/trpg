from typing import Any

from pydantic import BaseModel, ConfigDict

from src.db.repo import GraphRepo, ScenarioRepo
from src.game.domain.graph import AddNodeChange, GraphNode, apply_graph_change
from src.game.engines.graph_growth import (
    GraphGrowthError,
    GraphGrowthResult,
    plan_level_up,
    plan_skill_level_up,
)
from src.locale.render import render
from src.llm.diag import engine_diag, set_diag_context
from src.wire.graph.to_front import GraphFrontStatePayload, graph_to_front_state

from .apply import GraphRuntimeDirty, apply_runtime_graph_changes
from .cards import build_graph_level_up_card
from .load import load_runtime_state
from .state import GameRuntimeState


class GraphLevelUpError(ValueError):
    pass


class GraphLevelUpResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime: GameRuntimeState
    front_state: GraphFrontStatePayload


async def run_graph_level_up(
    repo: GraphRepo,
    game_id: str,
    *,
    growth: dict[str, Any],
    scenario_repo: ScenarioRepo | None = None,
) -> GraphLevelUpResult:
    runtime = await load_runtime_state(repo, game_id, scenario_repo)
    set_diag_context(game_id, runtime.progress.turn_count)
    engine_diag("levelup:start", growth=growth.get("kind"))
    if runtime.progress.pending_confirmation is not None:
        raise GraphLevelUpError("pending confirmation active")

    try:
        result, growth_label = _plan_growth_choice(runtime, growth)
    except GraphGrowthError as exc:
        engine_diag("levelup:fail", growth=growth.get("kind"), err=type(exc).__name__)
        raise GraphLevelUpError(str(exc)) from exc

    changes = result.changes
    applied = apply_runtime_graph_changes(runtime, changes)
    next_runtime = applied.runtime
    card = build_graph_level_up_card(
        next_runtime,
        growth_label,
        next_runtime.progress.next_log_id,
    )
    next_progress = next_runtime.progress.model_copy(
        update={"next_log_id": card.id + 1}
    )
    next_runtime = next_runtime.model_copy(
        update={
            "progress": next_progress,
            "log_entries": [*next_runtime.log_entries, card],
        }
    )

    await GraphRuntimeDirty.from_apply_result(applied).save(
        repo,
        game_id,
        next_runtime.graph,
    )
    await repo.append_log_entries(game_id, [card])
    await repo.save_progress(next_runtime.progress)
    player = next_runtime.graph.nodes[next_runtime.progress.player_id]
    level = player.properties.get("level")
    engine_diag(
        "levelup:ok",
        growth=growth.get("kind"),
        next_level=level if isinstance(level, int) else None,
    )
    return GraphLevelUpResult(
        runtime=next_runtime,
        front_state=graph_to_front_state(next_runtime),
    )


def _plan_growth_choice(
    runtime: GameRuntimeState,
    growth: dict[str, Any],
) -> tuple[GraphGrowthResult, str]:
    locale = runtime.progress.locale
    kind = growth.get("kind")
    if kind == "max_hp":
        result = plan_level_up(
            runtime.graph,
            runtime.progress.player_id,
            {"kind": "max_hp"},
        )
        return result, render("runtime.level_growth.max_hp", locale)
    if kind == "max_mp":
        result = plan_level_up(
            runtime.graph,
            runtime.progress.player_id,
            {"kind": "max_mp"},
        )
        return result, render("runtime.level_growth.max_mp", locale)
    if kind == "learn_skill":
        skill_id = _require_skill_id(growth)
        seed_change = _generated_skill_change(runtime, growth)
        graph = runtime.graph
        if seed_change is not None:
            graph = apply_graph_change(graph, seed_change)
        result = plan_skill_level_up(
            graph,
            runtime.progress.player_id,
            learn_skill_id=skill_id,
        )
        if seed_change is not None:
            result = result.model_copy(
                update={"changes": [seed_change, *result.changes]}
            )
        return result, render(
            "runtime.level_growth.learn_skill",
            locale,
            skill=_skill_label(runtime, skill_id),
        )
    if kind == "upgrade_skill":
        skill_id = _require_skill_id(growth)
        result = plan_skill_level_up(
            runtime.graph,
            runtime.progress.player_id,
            upgrade_skill_id=skill_id,
        )
        return result, render(
            "runtime.level_growth.upgrade_skill",
            locale,
            skill=_skill_label(runtime, skill_id),
        )
    raise GraphLevelUpError(f"unknown growth kind: {kind}")


def _require_skill_id(growth: dict[str, Any]) -> str:
    skill_id = growth.get("skill_id")
    if not isinstance(skill_id, str) or not skill_id:
        raise GraphLevelUpError("skill_id is required")
    return skill_id


def _generated_skill_change(
    runtime: GameRuntimeState,
    growth: dict[str, Any],
) -> AddNodeChange | None:
    skill = growth.get("skill")
    if not isinstance(skill, dict):
        return None
    skill_id = _require_skill_id(growth)
    if skill_id in runtime.graph.nodes:
        return None
    if skill.get("id") != skill_id:
        raise GraphLevelUpError("generated skill id mismatch")
    return AddNodeChange(
        type="add_node",
        node=GraphNode(
            id=skill_id,
            type="skill",
            properties={
                "name": _require_str(skill, "name"),
                "description": _require_str(skill, "description"),
                "kind": "support",
                "action": _require_choice(
                    skill,
                    "action",
                    {"attack", "defend", "flee", "social"},
                ),
                "mp_cost": _require_int(skill, "mp_cost", 1, 3),
                "effect_template": _require_choice(
                    skill,
                    "effect_template",
                    {
                        "dc_down",
                        "extra_heart_damage",
                        "prevent_heart_loss",
                        "escape_boost",
                    },
                ),
                "support_bonus": _require_int(skill, "support_bonus", 1, 3),
                "tags": _tags(skill.get("tags")),
            },
        ),
    )


def _require_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise GraphLevelUpError(f"generated skill {key} is required")
    return value.strip()


def _require_choice(data: dict[str, Any], key: str, choices: set[str]) -> str:
    value = _require_str(data, key)
    if value not in choices:
        raise GraphLevelUpError(f"invalid generated skill {key}: {value}")
    return value


def _require_int(data: dict[str, Any], key: str, minimum: int, maximum: int) -> int:
    value = data.get(key)
    if not isinstance(value, int) or value < minimum or value > maximum:
        raise GraphLevelUpError(f"invalid generated skill {key}: {value}")
    return value


def _tags(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [tag for tag in value if isinstance(tag, str) and tag][:4]


def _skill_label(runtime: GameRuntimeState, skill_id: str) -> str:
    node = runtime.graph.nodes.get(skill_id)
    if node is None:
        return skill_id
    name = node.properties.get("name")
    return name if isinstance(name, str) and name else skill_id
