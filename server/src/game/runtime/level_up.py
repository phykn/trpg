from pydantic import BaseModel, ConfigDict

from src.db.repo import GraphRepo, ScenarioRepo
from src.game.domain.types import GraphStatKey
from src.game.engines.graph_growth import GraphGrowthError, plan_level_up
from src.llm.diag import engine_diag, set_diag_context
from src.wire.graph_to_front import GraphFrontStatePayload, graph_to_front_state

from .apply import apply_runtime_graph_changes
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
    stat_up: GraphStatKey,
    skill_id: str | None,
    scenario_repo: ScenarioRepo | None = None,
) -> GraphLevelUpResult:
    if skill_id is not None:
        raise GraphLevelUpError("graph skill learning is not supported yet")

    runtime = await load_runtime_state(repo, game_id, scenario_repo)
    set_diag_context(game_id, runtime.progress.turn_count)
    engine_diag("levelup:start", stat=stat_up)
    if runtime.progress.pending_confirmation is not None:
        raise GraphLevelUpError("pending confirmation active")

    try:
        result = plan_level_up(runtime.graph, runtime.progress.player_id, stat_up)
    except GraphGrowthError as exc:
        engine_diag("levelup:fail", stat=stat_up, err=type(exc).__name__)
        raise GraphLevelUpError(str(exc)) from exc

    next_runtime = apply_runtime_graph_changes(runtime, result.changes).runtime
    card = build_graph_level_up_card(
        next_runtime,
        stat_up,
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

    await repo.save_graph(game_id, next_runtime.graph)
    await repo.append_log_entries(game_id, [card])
    await repo.save_progress(next_runtime.progress)
    player = next_runtime.graph.nodes[next_runtime.progress.player_id]
    level = player.properties.get("level")
    engine_diag("levelup:ok", stat=stat_up, next_level=level if isinstance(level, int) else None)
    return GraphLevelUpResult(
        runtime=next_runtime,
        front_state=graph_to_front_state(next_runtime),
    )
