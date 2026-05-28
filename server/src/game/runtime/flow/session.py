import secrets
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from src.db.repo import GraphRepo, ScenarioRepo
from src.game.domain.content import RuntimeContent
from src.game.domain.errors import LLMUnavailable
from src.game.domain.graph import Graph, GraphEdge, GraphNode
from src.game.domain.progress import GameProgress
from src.game.domain.story_contract import StoryContract
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
from src.locale.render import render
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
    contract_json = await scenario_repo.read_contract_json(profile, missing_ok=True)
    if contract_json is not None:
        contract = StoryContract.model_validate(contract_json)
        return await initialize_generated_session(
            profile,
            player,
            graph_repo,
            contract=contract,
            locale=locale,
        )
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


async def initialize_generated_session(
    profile: str,
    player: PlayerInput,
    graph_repo: GraphRepo,
    *,
    contract: StoryContract,
    locale: Literal["ko", "en"],
) -> GraphSessionSnapshot:
    game_id = _new_game_id()
    graph = _generated_graph(profile, player, locale)
    progress = GameProgress(
        game_id=game_id,
        player_id="player_01",
        profile_id=profile,
        locale=locale,
    )
    await graph_repo.save_progress(progress)
    await graph_repo.save_graph(game_id, graph)
    runtime = GameRuntimeState(
        graph=graph,
        progress=progress,
        content=RuntimeContent(),
        story_contract=contract,
    )
    set_diag_context(game_id, progress.turn_count)
    engine_diag("graph:init_generated_done", profile=profile)
    return GraphSessionSnapshot(
        game_id=game_id,
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


def _new_game_id() -> str:
    return datetime.now(timezone.utc).strftime(
        "game_%y%m%d_%H%M%S_"
    ) + secrets.token_hex(3)


def _generated_graph(profile: str, player: PlayerInput, locale: str) -> Graph:
    nodes = {
        "player_01": GraphNode(
            id="player_01",
            type="character",
            properties={
                "name": _player_value(player, "name")
                or render("runtime.generated.player.name", locale),
                "is_player": True,
                "level": 1,
                "gold": 0,
                "xp_pool": 0,
                "hp": 5,
                "max_hp": 5,
                "mp": 5,
                "max_mp": 5,
                "stats": {
                    "body": 1,
                    "agility": 1,
                    "mind": 1,
                    "presence": 1,
                },
            },
        ),
        "loc_fog_harbor": GraphNode(
            id="loc_fog_harbor",
            type="location",
            properties={
                "name": render("runtime.generated.loc_fog_harbor.name", locale),
                "description": render(
                    "runtime.generated.loc_fog_harbor.description",
                    locale,
                ),
            },
        ),
    }
    edges = {
        "located_at:player_01:loc_fog_harbor": GraphEdge(
            id="located_at:player_01:loc_fog_harbor",
            type="located_at",
            from_node_id="player_01",
            to_node_id="loc_fog_harbor",
        )
    }
    if profile == "white_isle_llm":
        nodes["npc_ellie"] = GraphNode(
            id="npc_ellie",
            type="character",
            properties={
                "name": render("runtime.generated.npc_ellie.name", locale),
                "alive": True,
                "level": 1,
                "hp": 5,
                "max_hp": 5,
                "mp": 5,
                "max_mp": 5,
                "stats": {
                    "body": 1,
                    "agility": 1,
                    "mind": 1,
                    "presence": 1,
                },
                "role": render("runtime.generated.npc_ellie.role", locale),
                "gender": "female",
                "race_job": render("runtime.generated.npc_ellie.race_job", locale),
            },
        )
        edges["located_at:npc_ellie:loc_fog_harbor"] = GraphEdge(
            id="located_at:npc_ellie:loc_fog_harbor",
            type="located_at",
            from_node_id="npc_ellie",
            to_node_id="loc_fog_harbor",
        )
    return Graph(nodes=nodes, edges=edges)


def _player_value(player: PlayerInput, field: str) -> str | None:
    if isinstance(player, dict):
        value = player.get(field)
    else:
        value = getattr(player, field, None)
    return value if isinstance(value, str) and value else None
