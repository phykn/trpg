from dataclasses import dataclass, field
from typing import Literal

from src.db.repo import GraphRepo, ScenarioRepo
from src.game.domain.errors import LLMUnavailable
from src.game.runtime.intro import (
    run_graph_initial_fallback_narration,
    run_graph_initial_narration,
)
from src.game.runtime.load import load_runtime_state
from src.game.runtime.state import GameRuntimeState
from src.game.seed.init_graph import init_graph_game
from src.game.seed.player import PlayerInput
from src.llm.client import LLMClient
from src.llm.diag import engine_diag, set_diag_context
from src.wire.graph_to_front import GraphFrontStatePayload, graph_to_front_state


@dataclass(frozen=True)
class GraphSessionSnapshot:
    game_id: str
    front_state: GraphFrontStatePayload


@dataclass(frozen=True)
class GraphSessionIntroResult:
    front_state: GraphFrontStatePayload
    status: Literal["executed"] = "executed"
    message: str | None = None
    suggestions: list[str] = field(default_factory=list)


async def initialize_graph_session(
    profile: str,
    player: PlayerInput,
    graph_repo: GraphRepo,
    scenario_repo: ScenarioRepo,
    *,
    locale: Literal["ko", "en"],
) -> GraphSessionSnapshot:
    set_diag_context("graph_init", 0)
    engine_diag("graph:init", profile=profile, locale=locale)
    bundle = await init_graph_game(
        profile,
        player,
        graph_repo,
        scenario_repo,
        locale=locale,
    )
    runtime = GameRuntimeState(
        graph=bundle.graph,
        progress=bundle.progress,
        content=bundle.content,
    )
    set_diag_context(bundle.progress.game_id, bundle.progress.turn_count)
    engine_diag("graph:init_seed_done", profile=profile)
    engine_diag("graph:init_done", logs=len(runtime.log_entries))
    return GraphSessionSnapshot(
        game_id=bundle.progress.game_id,
        front_state=graph_to_front_state(runtime),
    )


async def load_graph_session_state(
    repo: GraphRepo,
    game_id: str,
    scenario_repo: ScenarioRepo | None = None,
) -> GraphSessionSnapshot:
    set_diag_context(game_id, 0)
    engine_diag("state:load")
    runtime = await load_runtime_state(repo, game_id, scenario_repo)
    set_diag_context(game_id, runtime.progress.turn_count)
    engine_diag("state:done", logs=len(runtime.log_entries))
    return GraphSessionSnapshot(
        game_id=game_id,
        front_state=graph_to_front_state(runtime),
    )


async def run_graph_intro_request(
    llm: LLMClient,
    repo: GraphRepo,
    game_id: str,
    scenario_repo: ScenarioRepo | None = None,
) -> GraphSessionIntroResult:
    set_diag_context(game_id, 0)
    engine_diag("intro:load")
    runtime = await load_runtime_state(repo, game_id, scenario_repo)
    set_diag_context(game_id, runtime.progress.turn_count)
    engine_diag("intro:start")
    runtime = await _run_intro_or_fallback(llm, repo, runtime)
    engine_diag("intro:done", logs=len(runtime.log_entries))
    return GraphSessionIntroResult(front_state=graph_to_front_state(runtime))


async def _run_intro_or_fallback(
    llm: LLMClient,
    repo: GraphRepo,
    runtime: GameRuntimeState,
) -> GameRuntimeState:
    try:
        return await run_graph_initial_narration(llm, repo, runtime)
    except (LLMUnavailable, OSError, TimeoutError) as exc:
        engine_diag("intro:fallback", err=type(exc).__name__)
        return await run_graph_initial_fallback_narration(repo, runtime)
