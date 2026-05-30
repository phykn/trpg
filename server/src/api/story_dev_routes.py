"""Story development and generated-story diagnostic REST routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from src.db.repo import GraphRepo, ScenarioRepo
from src.game.domain.graph import Graph
from src.game.domain.story_contract import StoryContract
from src.game.domain.story_debt import build_story_debt_report
from src.game.domain.story_patch_ledger import StoryPatchLedgerEntry
from src.game.engines.story_patch_apply import (
    changed_edge_ids as _changed_edge_ids,
    changed_node_ids as _changed_node_ids,
    story_patches_to_graph_changes,
)
from src.game.engines.story_patch_validator import validate_story_write_response
from src.game.runtime.flow.generated_input import story_write_intent_for_contract
from src.game.runtime.load import load_runtime_state
from src.llm.calls.runner import get_prompt
from src.llm.context.story_write_context import build_story_write_input

from .deps import get_graph_repo, get_scenario_repo
from .schema import (
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
        player_id=runtime.progress.player_id,
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
