import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from ..errors import (
    InventoryInvalid,
    LevelUpInvalid,
    ProfileNotFound,
    RaceNotFound,
)
from ..mapping.to_front import to_front_state
from ..pipeline import inventory as inventory_engine
from ..pipeline.growth import level_up
from ..pipeline.turn import run_intro, run_roll, run_turn
from ..state.init import init_game
from ..state.store import load_game, read_current_game_id, save_entity, save_meta
from .auth import require_basic_auth
from .schema import (
    ChatRequest,
    ChatResponse,
    EquipRequest,
    InitRequest,
    InitResponse,
    InventoryResponse,
    LevelUpRequest,
    LevelUpResponse,
    ProfileCard,
    TradeRequest,
    TurnRequest,
    UnequipRequest,
)
from .sse import streaming_response

router = APIRouter()
protected = APIRouter(dependencies=[Depends(require_basic_auth)])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# --- profiles --------------------------------------------------------------


def _scan_profiles(profile_dir: str) -> list[dict]:
    pdir = Path(profile_dir)
    out: list[dict] = []
    if not pdir.is_dir():
        return out
    for sub in sorted(pdir.iterdir()):
        meta_file = sub / "profile.json"
        if not sub.is_dir() or not meta_file.exists():
            continue
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        races: list[dict] = []
        races_dir = sub / "races"
        if races_dir.is_dir():
            for rf in sorted(races_dir.glob("*.json")):
                rd = json.loads(rf.read_text(encoding="utf-8"))
                races.append(
                    {
                        "id": rd.get("id"),
                        "name": rd.get("name"),
                        "description": rd.get("description", ""),
                    }
                )
        out.append(
            {
                "id": meta.get("id", sub.name),
                "name": meta.get("name", sub.name),
                "description": meta.get("description", ""),
                "races": races,
            }
        )
    return out


@protected.get("/profiles", response_model=list[ProfileCard])
async def list_profiles(request: Request) -> list[dict]:
    return _scan_profiles(request.app.state.profile_dir)


# --- session ---------------------------------------------------------------


@protected.get("/session/current")
async def get_current_session(request: Request) -> dict:
    saves_dir = request.app.state.saves_dir
    game_id = read_current_game_id(saves_dir)
    if not game_id:
        raise HTTPException(status_code=404, detail="no current game")
    try:
        state = load_game(saves_dir, game_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="current game file missing")
    return {"game_id": state.game_id, "state": to_front_state(state)}


@protected.post("/session/init", response_model=InitResponse)
async def session_init(request: Request, body: InitRequest) -> InitResponse:
    try:
        state = await init_game(
            body.profile,
            body.player,
            request.app.state.saves_dir,
            request.app.state.profile_dir,
        )
    except ProfileNotFound as e:
        raise HTTPException(status_code=422, detail=f"profile not found: {e}")
    except RaceNotFound as e:
        raise HTTPException(status_code=422, detail=f"race not found: {e}")
    return InitResponse(game_id=state.game_id, state=to_front_state(state))


@protected.get("/session/{game_id}/state")
async def get_state(request: Request, game_id: str) -> dict:
    try:
        state = load_game(request.app.state.saves_dir, game_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    return {"game_id": state.game_id, "state": to_front_state(state)}


@protected.post("/session/{game_id}/turn")
async def session_turn(request: Request, game_id: str, body: TurnRequest):
    try:
        state = load_game(request.app.state.saves_dir, game_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    return streaming_response(
        run_turn(
            request.app.state.llm,
            state,
            request.app.state.profile_dir,
            request.app.state.saves_dir,
            body.player_input,
            to_front_fn=to_front_state,
        )
    )


@protected.post("/session/{game_id}/roll")
async def session_roll(request: Request, game_id: str):
    try:
        state = load_game(request.app.state.saves_dir, game_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    return streaming_response(
        run_roll(
            request.app.state.llm,
            state,
            request.app.state.profile_dir,
            request.app.state.saves_dir,
            to_front_fn=to_front_state,
        )
    )


@protected.post("/session/{game_id}/intro")
async def session_intro(request: Request, game_id: str):
    try:
        state = load_game(request.app.state.saves_dir, game_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    return streaming_response(
        run_intro(
            request.app.state.llm,
            state,
            request.app.state.profile_dir,
            request.app.state.saves_dir,
            to_front_fn=to_front_state,
        )
    )


@protected.post("/session/{game_id}/level-up", response_model=LevelUpResponse)
async def session_level_up(
    request: Request, game_id: str, body: LevelUpRequest
) -> LevelUpResponse:
    try:
        state = load_game(request.app.state.saves_dir, game_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    player = state.characters[state.player_id]
    try:
        level_up(player, body.stat_up, body.stat_down)  # type: ignore[arg-type]
    except LevelUpInvalid as e:
        raise HTTPException(status_code=422, detail=str(e))
    await save_entity(state, request.app.state.saves_dir, "characters", state.player_id)
    await save_meta(state, request.app.state.saves_dir)
    return LevelUpResponse(game_id=state.game_id, state=to_front_state(state))


@protected.post("/session/{game_id}/equip", response_model=InventoryResponse)
async def session_equip(
    request: Request, game_id: str, body: EquipRequest
) -> InventoryResponse:
    try:
        state = load_game(request.app.state.saves_dir, game_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    player = state.characters[state.player_id]
    try:
        inventory_engine.equip(player, body.item_id, body.slot, state.items)  # type: ignore[arg-type]
    except InventoryInvalid as e:
        raise HTTPException(status_code=422, detail=str(e))
    await save_entity(state, request.app.state.saves_dir, "characters", state.player_id)
    await save_meta(state, request.app.state.saves_dir)
    return InventoryResponse(game_id=state.game_id, state=to_front_state(state))


@protected.post("/session/{game_id}/unequip", response_model=InventoryResponse)
async def session_unequip(
    request: Request, game_id: str, body: UnequipRequest
) -> InventoryResponse:
    try:
        state = load_game(request.app.state.saves_dir, game_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    player = state.characters[state.player_id]
    try:
        inventory_engine.unequip(player, body.slot, state.items)  # type: ignore[arg-type]
    except InventoryInvalid as e:
        raise HTTPException(status_code=422, detail=str(e))
    await save_entity(state, request.app.state.saves_dir, "characters", state.player_id)
    await save_meta(state, request.app.state.saves_dir)
    return InventoryResponse(game_id=state.game_id, state=to_front_state(state))


@protected.post("/session/{game_id}/buy", response_model=InventoryResponse)
async def session_buy(
    request: Request, game_id: str, body: TradeRequest
) -> InventoryResponse:
    try:
        state = load_game(request.app.state.saves_dir, game_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    player = state.characters[state.player_id]
    npc = state.characters.get(body.npc_id)
    if npc is None:
        raise HTTPException(status_code=422, detail=f"unknown npc: {body.npc_id}")
    try:
        price = inventory_engine.buy(player, npc, body.item_id, state.items)
    except InventoryInvalid as e:
        raise HTTPException(status_code=422, detail=str(e))
    saves_dir = request.app.state.saves_dir
    await save_entity(state, saves_dir, "characters", state.player_id)
    await save_entity(state, saves_dir, "characters", npc.id)
    await save_meta(state, saves_dir)
    return InventoryResponse(game_id=state.game_id, state=to_front_state(state), price=price)


@protected.post("/session/{game_id}/sell", response_model=InventoryResponse)
async def session_sell(
    request: Request, game_id: str, body: TradeRequest
) -> InventoryResponse:
    try:
        state = load_game(request.app.state.saves_dir, game_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="game not found")
    player = state.characters[state.player_id]
    npc = state.characters.get(body.npc_id)
    if npc is None:
        raise HTTPException(status_code=422, detail=f"unknown npc: {body.npc_id}")
    try:
        price = inventory_engine.sell(player, npc, body.item_id, state.items)
    except InventoryInvalid as e:
        raise HTTPException(status_code=422, detail=str(e))
    saves_dir = request.app.state.saves_dir
    await save_entity(state, saves_dir, "characters", state.player_id)
    await save_entity(state, saves_dir, "characters", npc.id)
    await save_meta(state, saves_dir)
    return InventoryResponse(game_id=state.game_id, state=to_front_state(state), price=price)


@protected.post("/debug/complete", response_model=ChatResponse)
async def debug_complete(request: Request, body: ChatRequest) -> ChatResponse:
    result = await request.app.state.llm.complete(body.system, body.query, body.think)
    return ChatResponse(**result)


router.include_router(protected)
