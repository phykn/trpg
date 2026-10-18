"""Authenticated HTTP boundary: request schemas, routes, and error mapping."""

import json
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.content.schema import Approach
from src.locale import ko
from src.models.kev import ModelUnavailable
from src.scene.view import Button, GameView
from src.service import GameService, Stale
from src.store import SaveError
from src.world.state import IncompatibleSave

security = HTTPBasic()


def authenticate(request: Request, creds: Annotated[HTTPBasicCredentials, Depends(security)]) -> None:
    user_ok = secrets.compare_digest(creds.username.encode(), request.app.state.basic_auth_user.encode())
    pass_ok = secrets.compare_digest(creds.password.encode(), request.app.state.basic_auth_pass.encode())
    if not (user_ok and pass_ok):
        raise HTTPException(401, "invalid credentials", headers={"WWW-Authenticate": "Basic"})


def service(request: Request) -> GameService:
    return request.app.state.service


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StartRequest(Strict):
    story: str = Field(min_length=1, max_length=60)
    approaches: dict[Approach, int] | None = None
    traits: list[str] | None = Field(default=None, max_length=2)


class ActRequest(Strict):
    revision: int = Field(ge=0)
    request_id: str = Field(min_length=8, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    text: str | None = Field(default=None, max_length=200)
    action_id: str | None = Field(default=None, min_length=1, max_length=120)
    confirm: str | None = Field(default=None, min_length=1, max_length=60)
    accept: bool = True

    @model_validator(mode="after")
    def one_command(self):
        if self.text is not None:
            self.text = self.text.strip()
            if not self.text or any(ord(c) < 32 for c in self.text):
                raise ValueError("text must contain visible characters")
        if sum(v is not None for v in (self.text, self.action_id, self.confirm)) != 1:
            raise ValueError("send exactly one of text, action_id, confirm")
        return self


class ActResponse(Strict):
    kind: str
    view: GameView
    turn: int | None = None
    options: list[Button] = Field(default_factory=list)
    reason: str = ""


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, FileNotFoundError):
        return HTTPException(404, ko.ERRORS["missing"])
    if isinstance(exc, IncompatibleSave):
        return HTTPException(409, ko.ERRORS["version"])
    if isinstance(exc, Stale):
        return HTTPException(409, ko.ERRORS["stale"])
    if isinstance(exc, ModelUnavailable):
        return HTTPException(503, ko.ERRORS["model"])
    if isinstance(exc, SaveError):
        return HTTPException(503, ko.ERRORS["save"])
    return HTTPException(422, ko.ERRORS["invalid"])


HANDLED = (FileNotFoundError, ValueError, SaveError, ModelUnavailable)
router = APIRouter(dependencies=[Depends(authenticate)])
Service = Annotated[GameService, Depends(service)]


@router.get("/catalog")
async def catalog(game: Service) -> list[dict]:
    return game.catalog()


@router.post("/games", response_model=GameView)
async def start(body: StartRequest, game: Service):
    try:
        return await game.start(body.story, body.approaches, body.traits)
    except HANDLED as exc:
        raise _error(exc) from exc


@router.get("/games/{game_id}", response_model=GameView)
async def load(game_id: str, game: Service):
    try:
        return await game.load(game_id)
    except HANDLED as exc:
        raise _error(exc) from exc


@router.post("/games/{game_id}/act", response_model=ActResponse)
async def act(game_id: str, body: ActRequest, game: Service):
    try:
        out = await game.act(game_id, revision=body.revision, request_id=body.request_id, text=body.text,
                             action_id=body.action_id, confirm=body.confirm, accept=body.accept)
    except HANDLED as exc:
        raise _error(exc) from exc
    return ActResponse(kind=out.kind, view=out.view, turn=out.turn, options=out.options, reason=out.reason)


@router.get("/games/{game_id}/turns/{n}/narration")
async def narration(game_id: str, n: int, game: Service):
    try:
        await game.load(game_id)
    except HANDLED as exc:
        raise _error(exc) from exc

    async def lines():
        async for event in game.narration(game_id, n):
            yield json.dumps(event, ensure_ascii=False) + "\n"

    return StreamingResponse(lines(), media_type="application/x-ndjson")
