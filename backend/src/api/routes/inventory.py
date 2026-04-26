"""Inventory routes — equip/unequip/buy/sell/cast/use."""
from fastapi import APIRouter, Depends, HTTPException

from ...domain.errors import InventoryInvalid, SkillInvalid
from ...domain.state import GameState
from ...engines import inventory as inventory_engine
from ...engines import skill as skill_engine
from ...mapping.to_front import to_front_state
from ...persistence.store import save_entity, save_meta
from ..deps import get_saves_dir, get_state
from ..schema import (
    CastRequest,
    CastResponse,
    EquipRequest,
    InventoryResponse,
    TradeRequest,
    UnequipRequest,
    UseRequest,
    UseResponse,
)

router = APIRouter()


async def _save_player(state: GameState, saves_dir: str) -> None:
    await save_entity(state, saves_dir, "characters", state.player_id)
    await save_meta(state, saves_dir)


async def _save_trade(state: GameState, saves_dir: str, npc_id: str) -> None:
    await save_entity(state, saves_dir, "characters", state.player_id)
    await save_entity(state, saves_dir, "characters", npc_id)
    await save_meta(state, saves_dir)


async def _save_dirty(
    state: GameState, saves_dir: str, dirty: set[tuple[str, str]]
) -> None:
    for kind, eid in dirty:
        await save_entity(state, saves_dir, kind, eid)
    await save_meta(state, saves_dir)


@router.post("/session/{game_id}/equip", response_model=InventoryResponse)
async def session_equip(
    body: EquipRequest,
    state: GameState = Depends(get_state),
    saves_dir: str = Depends(get_saves_dir),
) -> InventoryResponse:
    player = state.characters[state.player_id]
    try:
        inventory_engine.equip(player, body.item_id, body.slot, state.items)  # type: ignore[arg-type]
    except InventoryInvalid as e:
        raise HTTPException(status_code=422, detail=str(e))
    await _save_player(state, saves_dir)
    return InventoryResponse(game_id=state.game_id, state=to_front_state(state))


@router.post("/session/{game_id}/unequip", response_model=InventoryResponse)
async def session_unequip(
    body: UnequipRequest,
    state: GameState = Depends(get_state),
    saves_dir: str = Depends(get_saves_dir),
) -> InventoryResponse:
    player = state.characters[state.player_id]
    try:
        inventory_engine.unequip(player, body.slot, state.items)  # type: ignore[arg-type]
    except InventoryInvalid as e:
        raise HTTPException(status_code=422, detail=str(e))
    await _save_player(state, saves_dir)
    return InventoryResponse(game_id=state.game_id, state=to_front_state(state))


@router.post("/session/{game_id}/buy", response_model=InventoryResponse)
async def session_buy(
    body: TradeRequest,
    state: GameState = Depends(get_state),
    saves_dir: str = Depends(get_saves_dir),
) -> InventoryResponse:
    player = state.characters[state.player_id]
    npc = state.characters.get(body.npc_id)
    if npc is None:
        raise HTTPException(status_code=422, detail=f"unknown npc: {body.npc_id}")
    try:
        price = inventory_engine.buy(player, npc, body.item_id, state.items)
    except InventoryInvalid as e:
        raise HTTPException(status_code=422, detail=str(e))
    await _save_trade(state, saves_dir, npc.id)
    return InventoryResponse(
        game_id=state.game_id, state=to_front_state(state), price=price
    )


@router.post("/session/{game_id}/sell", response_model=InventoryResponse)
async def session_sell(
    body: TradeRequest,
    state: GameState = Depends(get_state),
    saves_dir: str = Depends(get_saves_dir),
) -> InventoryResponse:
    player = state.characters[state.player_id]
    npc = state.characters.get(body.npc_id)
    if npc is None:
        raise HTTPException(status_code=422, detail=f"unknown npc: {body.npc_id}")
    try:
        price = inventory_engine.sell(player, npc, body.item_id, state.items)
    except InventoryInvalid as e:
        raise HTTPException(status_code=422, detail=str(e))
    await _save_trade(state, saves_dir, npc.id)
    return InventoryResponse(
        game_id=state.game_id, state=to_front_state(state), price=price
    )


@router.post("/session/{game_id}/cast", response_model=CastResponse)
async def session_cast(
    body: CastRequest,
    state: GameState = Depends(get_state),
    saves_dir: str = Depends(get_saves_dir),
) -> CastResponse:
    player = state.characters[state.player_id]
    dirty: set[tuple[str, str]] = set()
    try:
        result = skill_engine.cast(
            player, body.skill_id, state, body.targets, dirty=dirty
        )
    except SkillInvalid as e:
        raise HTTPException(status_code=422, detail=str(e))
    await _save_dirty(state, saves_dir, dirty)
    return CastResponse(
        game_id=state.game_id, state=to_front_state(state), result=result
    )


@router.post("/session/{game_id}/use", response_model=UseResponse)
async def session_use(
    body: UseRequest,
    state: GameState = Depends(get_state),
    saves_dir: str = Depends(get_saves_dir),
) -> UseResponse:
    player = state.characters[state.player_id]
    target = state.characters.get(body.target_id) if body.target_id else None
    if body.target_id and target is None:
        raise HTTPException(status_code=422, detail=f"unknown target: {body.target_id}")
    dirty: set[tuple[str, str]] = set()
    try:
        result = inventory_engine.use_with_quest_hook(
            player, body.item_id, target, state.items, state, dirty=dirty
        )
    except InventoryInvalid as e:
        raise HTTPException(status_code=422, detail=str(e))
    await _save_dirty(state, saves_dir, dirty)
    return UseResponse(
        game_id=state.game_id, state=to_front_state(state), result=result
    )
