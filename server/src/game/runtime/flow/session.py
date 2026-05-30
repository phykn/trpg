from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal

from src.db.repo import GraphRepo, ScenarioRepo
from src.game.domain.errors import LLMUnavailable
from src.game.domain.story_contract import StoryContract
from .generated_session import initialize_contract_generated_runtime
from .intro import (
    run_graph_initial_fallback_narration,
    run_graph_initial_narration,
    run_graph_initial_narration_stream,
)
from ..load import load_runtime_state
from ..request_result import GraphResultOutcome
from ..state import GameRuntimeState
from ..narration.suggestions import (
    GraphSuggestion,
    build_intro_suggestions,
    next_turn_suggestions,
)
from src.game.seed.init_graph import init_graph_game
from src.game.seed.player import PlayerInput
from src.llm.diag import engine_diag, set_diag_context
from src.wire.graph.to_front import GraphFrontStatePayload, graph_to_front_state


@dataclass(frozen=True)
class GraphSessionSnapshot:
    game_id: str
    front_state: GraphFrontStatePayload
    suggestions: list[GraphSuggestion] = field(default_factory=list)


@dataclass(frozen=True)
class GraphSessionIntroResult:
    front_state: GraphFrontStatePayload
    status: Literal["executed"] = "executed"
    outcome: GraphResultOutcome = "neutral"
    message: str | None = None
    suggestions: list[GraphSuggestion] = field(default_factory=list)


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
    player = PlayerInput.model_validate(player)
    contract_json = await scenario_repo.read_contract_json(profile, missing_ok=True)
    if contract_json is not None:
        contract = StoryContract.model_validate(contract_json)
        if not await _profile_has_seed(scenario_repo, profile):
            runtime = await initialize_contract_generated_runtime(
                profile,
                player,
                graph_repo,
                contract=contract,
                locale=locale,
            )
            set_diag_context(runtime.progress.game_id, runtime.progress.turn_count)
            engine_diag("graph:init_generated_done", profile=profile)
            return GraphSessionSnapshot(
                game_id=runtime.progress.game_id,
                front_state=graph_to_front_state(runtime),
            )
        return await _initialize_seed_session(
            profile,
            player,
            graph_repo,
            scenario_repo,
            locale=locale,
            story_contract=contract,
        )
    return await _initialize_seed_session(
        profile,
        player,
        graph_repo,
        scenario_repo,
        locale=locale,
        story_contract=None,
    )


async def _initialize_seed_session(
    profile: str,
    player: PlayerInput,
    graph_repo: GraphRepo,
    scenario_repo: ScenarioRepo,
    *,
    locale: Literal["ko", "en"],
    story_contract: StoryContract | None,
) -> GraphSessionSnapshot:
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
        story_contract=story_contract,
    )
    set_diag_context(bundle.progress.game_id, bundle.progress.turn_count)
    engine_diag("graph:init_seed_done", profile=profile)
    engine_diag("graph:init_done", logs=len(runtime.log_entries))
    return GraphSessionSnapshot(
        game_id=bundle.progress.game_id,
        front_state=graph_to_front_state(runtime),
    )


async def _profile_has_seed(scenario_repo: ScenarioRepo, profile: str) -> bool:
    try:
        await scenario_repo.read_start_json(profile)
        await scenario_repo.read_player(profile)
    except FileNotFoundError:
        return False
    return True


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
        suggestions=next_turn_suggestions(runtime, []),
    )


async def run_graph_intro_request(
    repo: GraphRepo,
    game_id: str,
    scenario_repo: ScenarioRepo | None = None,
) -> GraphSessionIntroResult:
    set_diag_context(game_id, 0)
    engine_diag("intro:load")
    runtime = await load_runtime_state(repo, game_id, scenario_repo)
    set_diag_context(game_id, runtime.progress.turn_count)
    engine_diag("intro:start")
    runtime = await _run_intro_or_fallback(repo, runtime)
    engine_diag("intro:done", logs=len(runtime.log_entries))
    return GraphSessionIntroResult(
        front_state=graph_to_front_state(runtime),
        suggestions=build_intro_suggestions(runtime),
    )


async def run_graph_intro_request_stream(
    repo: GraphRepo,
    game_id: str,
    scenario_repo: ScenarioRepo | None = None,
) -> AsyncIterator[dict[str, object]]:
    set_diag_context(game_id, 0)
    engine_diag("intro:load")
    runtime = await load_runtime_state(repo, game_id, scenario_repo)
    set_diag_context(game_id, runtime.progress.turn_count)
    engine_diag("intro:start")
    yield {
        "type": "result",
        "result": GraphSessionIntroResult(front_state=graph_to_front_state(runtime)),
    }
    try:
        async for event in run_graph_initial_narration_stream(repo, runtime):
            if event["type"] != "final":
                yield event
                continue
            next_runtime = event["runtime"]
            if not isinstance(next_runtime, GameRuntimeState):
                continue
            engine_diag("intro:done", logs=len(next_runtime.log_entries))
            yield {
                "type": "final",
                "result": GraphSessionIntroResult(
                    front_state=graph_to_front_state(next_runtime),
                    suggestions=build_intro_suggestions(next_runtime),
                ),
            }
    except (LLMUnavailable, OSError, TimeoutError) as exc:
        engine_diag("intro:fallback", err=type(exc).__name__)
        runtime = await run_graph_initial_fallback_narration(repo, runtime)
        engine_diag("intro:done", logs=len(runtime.log_entries))
        yield {
            "type": "final",
            "result": GraphSessionIntroResult(
                front_state=graph_to_front_state(runtime),
                suggestions=build_intro_suggestions(runtime),
            ),
        }


async def _run_intro_or_fallback(
    repo: GraphRepo,
    runtime: GameRuntimeState,
) -> GameRuntimeState:
    try:
        return await run_graph_initial_narration(repo, runtime)
    except (LLMUnavailable, OSError, TimeoutError) as exc:
        engine_diag("intro:fallback", err=type(exc).__name__)
        return await run_graph_initial_fallback_narration(repo, runtime)
