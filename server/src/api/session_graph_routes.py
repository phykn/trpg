"""Graph session REST routes."""

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from src.db.repo import GraphRepo, ScenarioRepo
from src.game.domain.errors import (
    ProfileMalformed,
    ProfileNotFound,
    RaceNotFound,
)
from src.game.runtime.action.combat_command import (
    CombatCommandError,
    build_combat_command_action,
)
from src.game.runtime.flow.confirmation import (
    GraphConfirmationActive,
    GraphConfirmationError,
    GraphConfirmationExpected,
    run_graph_action_request,
    run_graph_action_request_stream,
    run_graph_confirm,
    run_graph_confirm_stream,
)
from src.game.runtime.flow.input import (
    GraphInputError,
    run_graph_input_turn,
    run_graph_input_turn_stream,
)
from src.game.runtime.flow.generated_input import story_write_intent_for_contract
from src.game.runtime.flow.level_up import GraphLevelUpError, run_graph_level_up
from src.game.runtime.flow.level_up_choices import build_level_up_choices
from src.game.runtime.load import load_runtime_state
from src.game.domain.graph import Graph
from src.game.domain.story_debt import build_story_debt_report
from src.game.domain.story_patch_ledger import StoryPatchLedgerEntry
from src.game.engines.story_patch_apply import story_patches_to_graph_changes
from src.game.engines.story_patch_validator import validate_story_write_response
from src.game.runtime.flow.roll import (
    GraphRollError,
    GraphRollExpected,
    run_graph_roll,
    run_graph_roll_stream,
)
from src.game.runtime.flow.session import (
    initialize_graph_session,
    load_graph_session_state,
    run_graph_intro_request,
    run_graph_intro_request_stream,
)
from src.game.runtime.flow.turn import GraphActionTurnError
from src.game.domain.story_contract import StoryContract
from src.locale.render import render
from src.llm.calls.runner import get_prompt
from src.llm.client import LLMClient, force_think
from src.llm.context.story_write_context import build_story_write_input
from src.llm.diag import engine_diag

from .deps import get_graph_repo, get_llm, get_scenario_repo
from .schema import (
    ConfirmRequest,
    GraphActionResponse,
    GraphCombatCommandRequest,
    GraphInputRequest,
    GraphLevelUpChoicesResponse,
    GraphLevelUpRequest,
    GraphRollRequest,
    GraphTurnRequest,
    InitRequest,
    InitResponse,
    StoryContractPreviewRequest,
    StoryContractPreviewResponse,
    StoryContractResponse,
    StoryDebtResponse,
    StoryGraphResponse,
    StoryPatchEntriesResponse,
    StoryPatchPreviewRequest,
    StoryPatchPreviewResponse,
    StoryPromptReplayRequest,
    StoryPromptReplayResponse,
    StoryRollbackResponse,
)

router = APIRouter()

_PLAYER_ERROR_KEYS = {
    "a pending_confirmation is already active; call graph confirm instead": (
        "error.graph_pending_confirmation_active"
    ),
    "a pending_roll is already active; call graph roll instead": (
        "error.graph_pending_roll_active"
    ),
    "a pending_confirmation is already active": (
        "error.graph_pending_confirmation_active"
    ),
    "a pending_roll is already active": "error.graph_pending_roll_active",
    "no pending_confirmation": "error.graph_no_pending_confirmation",
    "confirmation id mismatch": "error.graph_confirmation_id_mismatch",
    "no pending_roll": "error.graph_no_pending_roll",
    "roll id mismatch": "error.graph_roll_id_mismatch",
    "not enough xp:": "error.graph_not_enough_xp",
    "protected target cannot be attacked": "log.error.protected_target",
}


def _request_thinking(enabled: bool) -> bool | None:
    return True if enabled else None


@router.post("/session/graph/init", response_model=InitResponse)
async def session_graph_init(
    body: InitRequest,
    graph_repo: GraphRepo = Depends(get_graph_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> InitResponse:
    try:
        result = await initialize_graph_session(
            body.profile, body.player, graph_repo, scenario_repo, locale=body.locale
        )
    except ProfileNotFound as e:
        raise HTTPException(status_code=422, detail=f"profile not found: {e}")
    except RaceNotFound as e:
        raise HTTPException(status_code=422, detail=f"race not found: {e}")
    except ProfileMalformed as e:
        raise HTTPException(status_code=422, detail=f"profile malformed: {e}")
    return InitResponse(
        game_id=result.game_id,
        state=result.front_state.model_dump(mode="json", by_alias=True),
        suggestions=result.suggestions,
    )


@router.post("/session/{game_id}/graph/intro", response_model=GraphActionResponse)
async def session_graph_intro(
    game_id: str,
    graph_repo: GraphRepo = Depends(get_graph_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> GraphActionResponse:
    try:
        result = await run_graph_intro_request(graph_repo, game_id, scenario_repo)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    return _graph_action_response(game_id, result)


@router.post("/session/{game_id}/graph/intro/stream")
async def session_graph_intro_stream(
    game_id: str,
    graph_repo: GraphRepo = Depends(get_graph_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> StreamingResponse:
    async def source():
        async for event in run_graph_intro_request_stream(
            graph_repo,
            game_id,
            scenario_repo,
        ):
            yield event

    return _graph_action_streaming_response(game_id, source)


@router.get("/session/{game_id}/graph/state", response_model=InitResponse)
async def get_graph_state_route(
    game_id: str,
    graph_repo: GraphRepo = Depends(get_graph_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> InitResponse:
    try:
        result = await load_graph_session_state(graph_repo, game_id, scenario_repo)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    return InitResponse(
        game_id=result.game_id,
        state=result.front_state.model_dump(mode="json", by_alias=True),
        suggestions=result.suggestions,
    )


@router.get(
    "/session/{game_id}/story/patches",
    response_model=StoryPatchEntriesResponse,
)
async def get_story_patch_entries_route(
    game_id: str,
    graph_repo: GraphRepo = Depends(get_graph_repo),
) -> StoryPatchEntriesResponse:
    return await _story_patch_entries_response(game_id, graph_repo)


@router.get(
    "/session/{game_id}/story/timeline",
    response_model=StoryPatchEntriesResponse,
)
async def get_story_patch_timeline_route(
    game_id: str,
    graph_repo: GraphRepo = Depends(get_graph_repo),
) -> StoryPatchEntriesResponse:
    return await _story_patch_entries_response(game_id, graph_repo)


@router.get(
    "/session/{game_id}/story/debt",
    response_model=StoryDebtResponse,
)
async def get_story_debt_route(
    game_id: str,
    graph_repo: GraphRepo = Depends(get_graph_repo),
) -> StoryDebtResponse:
    try:
        graph = await graph_repo.load_graph(game_id)
        await graph_repo.load_progress(game_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    return StoryDebtResponse(
        game_id=game_id,
        debt=build_story_debt_report(graph),
    )


@router.get(
    "/session/{game_id}/story/dev/graph",
    response_model=StoryGraphResponse,
)
async def get_story_graph_route(
    game_id: str,
    graph_repo: GraphRepo = Depends(get_graph_repo),
) -> StoryGraphResponse:
    try:
        graph = await graph_repo.load_graph(game_id)
        await graph_repo.load_progress(game_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    return StoryGraphResponse(game_id=game_id, graph=graph)


@router.get(
    "/session/{game_id}/story/dev/contract",
    response_model=StoryContractResponse,
)
async def get_story_contract_route(
    game_id: str,
    graph_repo: GraphRepo = Depends(get_graph_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> StoryContractResponse:
    try:
        runtime = await load_runtime_state(graph_repo, game_id, scenario_repo)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    if runtime.story_contract is None:
        raise HTTPException(status_code=409, detail="story contract not available")
    return StoryContractResponse(game_id=game_id, contract=runtime.story_contract)


@router.post(
    "/session/{game_id}/story/dev/preview_contract",
    response_model=StoryContractPreviewResponse,
)
async def preview_story_contract_route(
    game_id: str,
    body: StoryContractPreviewRequest,
    graph_repo: GraphRepo = Depends(get_graph_repo),
) -> StoryContractPreviewResponse:
    try:
        await graph_repo.load_progress(game_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    try:
        contract = StoryContract.model_validate(body.contract)
    except ValidationError as e:
        return StoryContractPreviewResponse(
            game_id=game_id,
            ok=False,
            reasons=[error["msg"] for error in e.errors()],
        )
    return StoryContractPreviewResponse(game_id=game_id, ok=True, contract=contract)


@router.post(
    "/session/{game_id}/story/dev/contract",
    response_model=StoryContractResponse,
)
async def update_story_contract_route(
    game_id: str,
    body: StoryContractPreviewRequest,
    graph_repo: GraphRepo = Depends(get_graph_repo),
) -> StoryContractResponse:
    try:
        progress = await graph_repo.load_progress(game_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    try:
        contract = StoryContract.model_validate(body.contract)
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=", ".join(error["msg"] for error in e.errors()),
        )
    await graph_repo.save_progress(
        progress.model_copy(
            update={
                "story_contract_override": contract.model_dump(
                    mode="json",
                    by_alias=True,
                )
            }
        )
    )
    return StoryContractResponse(game_id=game_id, contract=contract)


@router.post(
    "/session/{game_id}/story/rollback",
    response_model=StoryRollbackResponse,
)
async def rollback_story_patch_route(
    game_id: str,
    graph_repo: GraphRepo = Depends(get_graph_repo),
) -> StoryRollbackResponse:
    try:
        graph = await graph_repo.load_graph(game_id)
        progress = await graph_repo.load_progress(game_id)
        entries = await graph_repo.load_story_patch_entries(game_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    target = _last_unrolled_accepted_patch(entries)
    if target is None:
        raise HTTPException(
            status_code=409,
            detail="no accepted story patch to rollback",
        )
    next_graph = _graph_without_story_patch(graph, target)
    rollback_entry = StoryPatchLedgerEntry(
        turn=progress.turn_count,
        status="rolled_back",
        intent_kind=target.intent_kind,
        reason="rolled back accepted story patch",
        patches=target.patches,
        changed_node_ids=target.changed_node_ids,
        changed_edge_ids=target.changed_edge_ids,
    )
    await graph_repo.save_graph(game_id, next_graph)
    await graph_repo.append_story_patch_entries(game_id, [rollback_entry])
    return StoryRollbackResponse(game_id=game_id, entry=rollback_entry)


@router.post(
    "/session/{game_id}/story/dev/preview_patch",
    response_model=StoryPatchPreviewResponse,
)
async def preview_story_patch_route(
    game_id: str,
    body: StoryPatchPreviewRequest,
    graph_repo: GraphRepo = Depends(get_graph_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> StoryPatchPreviewResponse:
    try:
        runtime = await load_runtime_state(graph_repo, game_id, scenario_repo)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    if runtime.story_contract is None:
        raise HTTPException(
            status_code=409,
            detail="story contract not available",
        )
    validation = validate_story_write_response(
        body.proposal,
        graph=runtime.graph,
        contract=runtime.story_contract,
    )
    if not validation.ok:
        return StoryPatchPreviewResponse(
            game_id=game_id,
            ok=False,
            reasons=validation.reasons,
        )
    changes = story_patches_to_graph_changes(
        body.proposal.patches,
        graph=runtime.graph,
        player_id=runtime.progress.player_id,
        turn_id=runtime.progress.turn_count,
    )
    return StoryPatchPreviewResponse(
        game_id=game_id,
        ok=True,
        changed_node_ids=_changed_node_ids(changes),
        changed_edge_ids=_changed_edge_ids(changes),
    )


@router.post(
    "/session/{game_id}/story/dev/replay_prompt",
    response_model=StoryPromptReplayResponse,
)
async def replay_story_prompt_route(
    game_id: str,
    body: StoryPromptReplayRequest,
    graph_repo: GraphRepo = Depends(get_graph_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> StoryPromptReplayResponse:
    try:
        runtime = await load_runtime_state(graph_repo, game_id, scenario_repo)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    if runtime.story_contract is None:
        raise HTTPException(status_code=409, detail="story contract not available")
    intent = story_write_intent_for_contract(
        body.action,
        runtime.story_contract,
        runtime=runtime,
    )
    input_ = build_story_write_input(
        runtime,
        contract=runtime.story_contract,
        intent=intent,
        player_input=body.player_input,
        action=body.action,
    )
    return StoryPromptReplayResponse(
        game_id=game_id,
        intent=intent.model_dump(mode="json"),
        system_prompt=get_prompt("story_write", runtime.progress.locale),
        user_payload=input_.model_dump(mode="json"),
    )


async def _story_patch_entries_response(
    game_id: str,
    graph_repo: GraphRepo,
) -> StoryPatchEntriesResponse:
    try:
        await graph_repo.load_progress(game_id)
        entries = await graph_repo.load_story_patch_entries(game_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    return StoryPatchEntriesResponse(game_id=game_id, entries=entries)


def _last_unrolled_accepted_patch(
    entries: list[StoryPatchLedgerEntry],
) -> StoryPatchLedgerEntry | None:
    rolled_back = {
        _rollback_signature(entry)
        for entry in entries
        if entry.status == "rolled_back"
    }
    for entry in reversed(entries):
        if entry.status != "accepted":
            continue
        if _rollback_signature(entry) in rolled_back:
            continue
        if entry.changed_node_ids or entry.changed_edge_ids:
            return entry
    return None


def _rollback_signature(entry: StoryPatchLedgerEntry) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return (tuple(entry.changed_node_ids), tuple(entry.changed_edge_ids))


def _graph_without_story_patch(graph: Graph, entry: StoryPatchLedgerEntry) -> Graph:
    removed_nodes = set(entry.changed_node_ids)
    removed_edges = set(entry.changed_edge_ids)
    removed_edges.update(
        edge.id
        for edge in graph.edges.values()
        if edge.from_node_id in removed_nodes or edge.to_node_id in removed_nodes
    )
    return Graph(
        nodes={
            node_id: node
            for node_id, node in graph.nodes.items()
            if node_id not in removed_nodes
        },
        edges={
            edge_id: edge
            for edge_id, edge in graph.edges.items()
            if edge_id not in removed_edges
            and edge.from_node_id not in removed_nodes
            and edge.to_node_id not in removed_nodes
        },
    )


def _changed_node_ids(changes) -> list[str]:
    return [
        change.node.id
        for change in changes
        if getattr(change, "type", None) == "add_node"
    ]


def _changed_edge_ids(changes) -> list[str]:
    return [
        change.edge.id
        for change in changes
        if getattr(change, "type", None) == "add_edge"
    ]


@router.post("/session/{game_id}/graph/turn", response_model=GraphActionResponse)
async def session_graph_turn(
    game_id: str,
    body: GraphTurnRequest,
    llm: LLMClient = Depends(get_llm),
    graph_repo: GraphRepo = Depends(get_graph_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> GraphActionResponse:
    try:
        with force_think(_request_thinking(body.think)):
            result = await run_graph_action_request(
                graph_repo,
                game_id,
                body.action,
                llm=llm,
                scenario_repo=scenario_repo,
            )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    except GraphConfirmationActive as e:
        raise HTTPException(status_code=409, detail=_player_error_detail(e))
    except GraphConfirmationError as e:
        raise HTTPException(status_code=422, detail=_player_error_detail(e))
    except GraphActionTurnError as e:
        raise HTTPException(status_code=422, detail=_player_error_detail(e))
    return _graph_action_response(game_id, result)


@router.post("/session/{game_id}/graph/turn/stream")
async def session_graph_turn_stream(
    game_id: str,
    body: GraphTurnRequest,
    llm: LLMClient = Depends(get_llm),
    graph_repo: GraphRepo = Depends(get_graph_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> StreamingResponse:
    async def source():
        with force_think(_request_thinking(body.think)):
            async for event in run_graph_action_request_stream(
                graph_repo,
                game_id,
                body.action,
                llm=llm,
                scenario_repo=scenario_repo,
            ):
                yield event

    return _graph_action_streaming_response(game_id, source)


@router.post("/session/{game_id}/graph/combat", response_model=GraphActionResponse)
async def session_graph_combat(
    game_id: str,
    body: GraphCombatCommandRequest,
    llm: LLMClient = Depends(get_llm),
    graph_repo: GraphRepo = Depends(get_graph_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> GraphActionResponse:
    try:
        runtime = await load_runtime_state(graph_repo, game_id, scenario_repo)
        action = build_combat_command_action(
            runtime,
            body.model_dump(exclude={"think"}),
        )
        with force_think(_request_thinking(body.think)):
            result = await run_graph_action_request(
                graph_repo,
                game_id,
                action,
                llm=llm,
                scenario_repo=scenario_repo,
            )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    except GraphConfirmationActive as e:
        raise HTTPException(status_code=409, detail=_player_error_detail(e))
    except (CombatCommandError, GraphConfirmationError, GraphActionTurnError) as e:
        raise HTTPException(status_code=422, detail=_player_error_detail(e))
    return _graph_action_response(game_id, result)


@router.post("/session/{game_id}/graph/combat/stream")
async def session_graph_combat_stream(
    game_id: str,
    body: GraphCombatCommandRequest,
    llm: LLMClient = Depends(get_llm),
    graph_repo: GraphRepo = Depends(get_graph_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> StreamingResponse:
    async def source():
        runtime = await load_runtime_state(graph_repo, game_id, scenario_repo)
        action = build_combat_command_action(
            runtime,
            body.model_dump(exclude={"think"}),
        )
        with force_think(_request_thinking(body.think)):
            async for event in run_graph_action_request_stream(
                graph_repo,
                game_id,
                action,
                llm=llm,
                scenario_repo=scenario_repo,
            ):
                yield event

    return _graph_action_streaming_response(game_id, source)


@router.post("/session/{game_id}/graph/confirm", response_model=GraphActionResponse)
async def session_graph_confirm(
    game_id: str,
    body: ConfirmRequest,
    llm: LLMClient = Depends(get_llm),
    graph_repo: GraphRepo = Depends(get_graph_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> GraphActionResponse:
    try:
        with force_think(_request_thinking(body.think)):
            result = await run_graph_confirm(
                graph_repo,
                game_id,
                body.confirmation_id,
                body.decision,
                llm=llm,
                scenario_repo=scenario_repo,
            )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    except GraphConfirmationExpected as e:
        raise HTTPException(status_code=422, detail=_player_error_detail(e))
    except GraphConfirmationError as e:
        raise HTTPException(status_code=422, detail=_player_error_detail(e))
    return _graph_action_response(game_id, result)


@router.post("/session/{game_id}/graph/confirm/stream")
async def session_graph_confirm_stream(
    game_id: str,
    body: ConfirmRequest,
    llm: LLMClient = Depends(get_llm),
    graph_repo: GraphRepo = Depends(get_graph_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> StreamingResponse:
    async def source():
        with force_think(_request_thinking(body.think)):
            async for event in run_graph_confirm_stream(
                graph_repo,
                game_id,
                body.confirmation_id,
                body.decision,
                llm=llm,
                scenario_repo=scenario_repo,
            ):
                yield event

    return _graph_action_streaming_response(game_id, source)


@router.post("/session/{game_id}/graph/roll", response_model=GraphActionResponse)
async def session_graph_roll(
    game_id: str,
    body: GraphRollRequest,
    llm: LLMClient = Depends(get_llm),
    graph_repo: GraphRepo = Depends(get_graph_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> GraphActionResponse:
    try:
        result = await run_graph_roll(
            graph_repo,
            game_id,
            body.roll_id,
            llm=llm,
            scenario_repo=scenario_repo,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    except GraphRollExpected as e:
        raise HTTPException(status_code=422, detail=_player_error_detail(e))
    except GraphRollError as e:
        raise HTTPException(status_code=422, detail=_player_error_detail(e))
    return _graph_action_response(game_id, result)


@router.post("/session/{game_id}/graph/roll/stream")
async def session_graph_roll_stream(
    game_id: str,
    body: GraphRollRequest,
    llm: LLMClient = Depends(get_llm),
    graph_repo: GraphRepo = Depends(get_graph_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> StreamingResponse:
    async def source():
        async for event in run_graph_roll_stream(
            llm,
            graph_repo,
            game_id,
            body.roll_id,
            scenario_repo=scenario_repo,
        ):
            yield event

    return _graph_action_streaming_response(game_id, source)


@router.post("/session/{game_id}/graph/input", response_model=GraphActionResponse)
async def session_graph_input(
    game_id: str,
    body: GraphInputRequest,
    llm: LLMClient = Depends(get_llm),
    graph_repo: GraphRepo = Depends(get_graph_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> GraphActionResponse:
    try:
        with force_think(_request_thinking(body.think)):
            result = await run_graph_input_turn(
                llm,
                graph_repo,
                game_id,
                body.player_input,
                scenario_repo=scenario_repo,
            )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    except GraphConfirmationActive as e:
        raise HTTPException(status_code=409, detail=_player_error_detail(e))
    except (GraphInputError, GraphConfirmationError, GraphActionTurnError) as e:
        raise HTTPException(status_code=422, detail=_player_error_detail(e))
    return _graph_action_response(game_id, result)


@router.post("/session/{game_id}/graph/input/stream")
async def session_graph_input_stream(
    game_id: str,
    body: GraphInputRequest,
    llm: LLMClient = Depends(get_llm),
    graph_repo: GraphRepo = Depends(get_graph_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> StreamingResponse:
    async def source():
        with force_think(_request_thinking(body.think)):
            async for event in run_graph_input_turn_stream(
                llm,
                graph_repo,
                game_id,
                body.player_input,
                scenario_repo=scenario_repo,
            ):
                yield event

    return _graph_action_streaming_response(game_id, source)


def _graph_action_streaming_response(game_id, source) -> StreamingResponse:
    async def event_lines():
        try:
            async for event in source():
                yield _stream_event(game_id, event)
        except FileNotFoundError:
            yield _stream_error(404, "game not found")
        except GraphConfirmationActive as e:
            yield _stream_error(409, _player_error_detail(e))
        except GraphConfirmationExpected as e:
            yield _stream_error(422, _player_error_detail(e))
        except (
            CombatCommandError,
            GraphInputError,
            GraphConfirmationError,
            GraphActionTurnError,
            GraphRollError,
        ) as e:
            yield _stream_error(422, _player_error_detail(e))
        except Exception as e:
            engine_diag("graph_stream:fail", err=type(e).__name__)
            yield _stream_error(500, render("error.graph_stream_failed", "ko"))

    return StreamingResponse(event_lines(), media_type="application/x-ndjson")


def _player_error_detail(error: Exception) -> str:
    message = str(error)
    if message.startswith("missing location:"):
        return render("error.graph_location_unreachable", "ko")
    if "is not adjacent to current location" in message:
        return render("error.graph_location_unreachable", "ko")
    if "is locked from current location" in message:
        return render("error.graph_location_unreachable", "ko")
    for prefix, key in _PLAYER_ERROR_KEYS.items():
        if message.startswith(prefix):
            return render(key, "ko")
    return message


def _stream_event(game_id: str, event) -> str:
    event_type = event["type"]
    if event_type in {"result", "final"}:
        response = _graph_action_response(game_id, event["result"])
        payload = {
            "type": event_type,
            "payload": response.model_dump(mode="json"),
        }
    else:
        payload = event
    return json.dumps(payload, ensure_ascii=False) + "\n"


def _stream_error(status: int, message: str) -> str:
    return (
        json.dumps(
            {"type": "error", "status": status, "message": message},
            ensure_ascii=False,
        )
        + "\n"
    )


def _graph_action_response(game_id: str, result) -> GraphActionResponse:
    return GraphActionResponse(
        game_id=game_id,
        state=result.front_state.model_dump(mode="json", by_alias=True),
        status=result.status,
        outcome=result.outcome,
        message=result.message,
        suggestions=result.suggestions,
    )


@router.get(
    "/session/{game_id}/graph/level_up/options",
    response_model=GraphLevelUpChoicesResponse,
)
async def session_graph_level_up_options(
    game_id: str,
    llm: LLMClient = Depends(get_llm),
    graph_repo: GraphRepo = Depends(get_graph_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> GraphLevelUpChoicesResponse:
    try:
        runtime = await load_runtime_state(graph_repo, game_id, scenario_repo)
        choices = await build_level_up_choices(runtime, llm=llm)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    return GraphLevelUpChoicesResponse(choices=choices)


@router.post("/session/{game_id}/graph/level_up", response_model=GraphActionResponse)
async def session_graph_level_up(
    game_id: str,
    body: GraphLevelUpRequest,
    graph_repo: GraphRepo = Depends(get_graph_repo),
    scenario_repo: ScenarioRepo = Depends(get_scenario_repo),
) -> GraphActionResponse:
    try:
        result = await run_graph_level_up(
            graph_repo,
            game_id,
            growth=body.growth,
            scenario_repo=scenario_repo,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    except GraphLevelUpError as e:
        raise HTTPException(status_code=422, detail=_player_error_detail(e))
    return GraphActionResponse(
        game_id=game_id,
        state=result.front_state.model_dump(mode="json", by_alias=True),
        status=None,
        outcome="success",
        message=None,
    )
