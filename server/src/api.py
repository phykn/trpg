"""The HTTP boundary (api.md): Basic Auth, routes and the error table."""

from __future__ import annotations

import json
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .locale import ko
from .service import Conflict, GameService, Incompatible, Invalid, Missing

security = HTTPBasic()
REQUEST_ID = r"^[A-Za-z0-9_-]{1,64}$"


def authenticate(request: Request, creds: Annotated[HTTPBasicCredentials, Depends(security)]) -> None:
    user_ok = secrets.compare_digest(creds.username.encode(), request.app.state.basic_auth_user.encode())
    pass_ok = secrets.compare_digest(creds.password.encode(), request.app.state.basic_auth_pass.encode())
    if not (user_ok and pass_ok):
        raise HTTPException(401, "invalid credentials", headers={"WWW-Authenticate": "Basic"})


def service(request: Request) -> GameService:
    return request.app.state.service


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Creation(Strict):
    approaches: dict[str, int]
    traits: list[str] = Field(default_factory=list, max_length=8)


class CreateBody(Strict):
    request_id: str = Field(pattern=REQUEST_ID)
    story: str = Field(min_length=1, max_length=60)
    creation: Creation


class CommandBody(Strict):
    request_id: str = Field(pattern=REQUEST_ID)
    revision: int = Field(ge=0)
    text: str | None = Field(default=None, max_length=200)
    action: str | None = Field(default=None, min_length=1, max_length=200)
    card: str | None = Field(default=None, min_length=1, max_length=40)
    pick: str | None = Field(default=None, min_length=1, max_length=200)
    cancel: bool | None = None

    @model_validator(mode="after")
    def one_command(self):
        if self.text is not None:
            self.text = self.text.strip()
            if not self.text or any(ord(c) < 32 for c in self.text):
                raise ValueError("text must contain visible characters")
        if sum(v is not None for v in (self.text, self.action, self.card)) != 1:
            raise ValueError("send exactly one of text, action, card")
        if self.card is not None and (self.pick is None) == (self.cancel is not True):
            raise ValueError("a card answer is a pick or cancel: true")
        if self.card is None and (self.pick is not None or self.cancel is not None):
            raise ValueError("pick and cancel answer a card")
        return self

    def payload(self) -> dict:
        return {k: v for k, v in self.model_dump().items() if v is not None}


def _error(e: Exception) -> JSONResponse:
    if isinstance(e, Missing):
        return JSONResponse({"reason": ko.ERRORS["missing"]}, status_code=404)
    if isinstance(e, Incompatible):
        return JSONResponse({"reason": "incompatible"}, status_code=409)
    if isinstance(e, Conflict):
        return JSONResponse({"view": e.view}, status_code=409)
    return JSONResponse({"reason": str(e) or ko.ERRORS["invalid"]}, status_code=422)


HANDLED = (Missing, Incompatible, Conflict, Invalid)
router = APIRouter(dependencies=[Depends(authenticate)])
Service = Annotated[GameService, Depends(service)]


@router.get("/stories")
async def stories(game: Service) -> list[dict]:
    return game.catalog()


@router.post("/games")
async def create(body: CreateBody, game: Service):
    try:
        return await game.create(body.request_id, body.story, body.creation.model_dump())
    except HANDLED as e:
        return _error(e)


@router.get("/games/{game_id}")
async def get(game_id: str, game: Service):
    try:
        return await game.view(game_id)
    except HANDLED as e:
        return _error(e)


@router.post("/games/{game_id}/commands")
async def command(game_id: str, body: CommandBody, game: Service):
    try:
        return await game.command(game_id, body.payload())
    except HANDLED as e:
        return _error(e)


def _ndjson(events) -> StreamingResponse:
    async def lines():
        async for e in events:
            yield json.dumps(e, ensure_ascii=False) + "\n"
    return StreamingResponse(lines(), media_type="application/x-ndjson")


@router.get("/games/{game_id}/turns/{n}/narration")
async def narration(game_id: str, n: int, game: Service):
    try:
        return _ndjson(await game.narration(game_id, n))
    except HANDLED as e:
        return _error(e)


@router.get("/games/{game_id}/chapters/{k}/recap")
async def recap(game_id: str, k: int, game: Service):
    try:
        return _ndjson(await game.recap(game_id, k))
    except HANDLED as e:
        return _error(e)
