"""Authenticated HTTP commands for the harbor adventure."""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.game.models import IncompatibleSave
from src.locale.ko import text
from src.service import GameService, StaleChoice
from src.store import SaveError
from src.view import GameView

security = HTTPBasic()


def authenticate(
    request: Request, creds: Annotated[HTTPBasicCredentials, Depends(security)]
):
    if not (
        secrets.compare_digest(
            creds.username.encode(), request.app.state.basic_auth_user.encode()
        )
        and secrets.compare_digest(
            creds.password.encode(), request.app.state.basic_auth_pass.encode()
        )
    ):
        raise HTTPException(
            401, "invalid credentials", headers={"WWW-Authenticate": "Basic"}
        )


def runtime(request: Request) -> GameService:
    return request.app.state.adventure


class StartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=20)
    role: str = Field(max_length=40)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if not value or any(ord(char) < 32 for char in value):
            raise ValueError("name must contain visible characters")
        return value


class ChoiceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    option_id: str = Field(min_length=1, max_length=100)
    revision: int = Field(ge=0)
    request_id: str = Field(min_length=8, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")


router = APIRouter(prefix="/adventure", dependencies=[Depends(authenticate)])


@router.get("/catalog")
async def catalog(game: Annotated[GameService, Depends(runtime)]):
    story = game.story
    return {
        "title": story.title,
        "synopsis": story.synopsis,
        "roles": [
            {"id": key, "name": role.name, "text": role.text}
            for key, role in story.roles.items()
        ],
    }


def _error(exc):
    if isinstance(exc, FileNotFoundError):
        return HTTPException(404, text("missing"))
    if isinstance(exc, IncompatibleSave):
        return HTTPException(409, text("version"))
    if isinstance(exc, StaleChoice):
        return HTTPException(409, text("stale"))
    if isinstance(exc, SaveError):
        return HTTPException(503, text("save_error"))
    return HTTPException(422, text("invalid"))


@router.post("/start", response_model=GameView)
async def start(body: StartRequest, game: Annotated[GameService, Depends(runtime)]):
    try:
        return await game.start(body.name, body.role)
    except (ValueError, SaveError) as exc:
        raise _error(exc) from exc


@router.get("/{game_id}", response_model=GameView)
async def load(game_id: str, game: Annotated[GameService, Depends(runtime)]):
    try:
        return await game.load(game_id)
    except (FileNotFoundError, ValueError, SaveError) as exc:
        raise _error(exc) from exc


@router.post("/{game_id}/choose", response_model=GameView)
async def act(
    game_id: str,
    body: ChoiceRequest,
    game: Annotated[GameService, Depends(runtime)],
):
    try:
        return await game.act(game_id, body.option_id, body.revision, body.request_id)
    except (FileNotFoundError, ValueError, SaveError) as exc:
        raise _error(exc) from exc
