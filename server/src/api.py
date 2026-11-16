import json
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .ai import ModelUnavailable
from .game.service import Broken, Conflict, Missing

REQUEST_ID = r"^[A-Za-z0-9_-]{1,64}$"
ERRORS = {
    Missing: lambda _request, _exc: JSONResponse({}, 404),
    Conflict: lambda _request, exc: JSONResponse({"view": exc.view}, 409),
    Broken: lambda _request, exc: JSONResponse({"reason": exc.reason}, 409),
    ModelUnavailable: lambda _request, _exc: JSONResponse({}, 503),
    RequestValidationError: lambda _request, _exc: JSONResponse({"reason": "bad request"}, 422),
}


def build_app(cfg, service):
    app = FastAPI(title="TRPG")
    app.state.service = service
    app.state.auth = (cfg.basic_auth_user, cfg.basic_auth_pass)
    app.add_middleware(CORSMiddleware, allow_origins=cfg.cors_origins, allow_methods=["GET", "POST", "OPTIONS"],
                       allow_headers=["Authorization", "Content-Type", "Accept"])

    @app.get("/health")
    async def health():
        return {"ok": True}

    app.include_router(router)
    for error, reply in ERRORS.items():
        app.add_exception_handler(error, reply)
    return app


def authenticate(request: Request, creds: Annotated[HTTPBasicCredentials, Depends(HTTPBasic())]):
    user, password = request.app.state.auth
    user_ok = secrets.compare_digest(creds.username.encode(), user.encode())
    pass_ok = secrets.compare_digest(creds.password.encode(), password.encode())
    if not (user_ok and pass_ok):
        raise HTTPException(401, "invalid credentials", headers={"WWW-Authenticate": "Basic"})


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateBody(Strict):
    request_id: str = Field(pattern=REQUEST_ID)
    story: str = Field(min_length=1, max_length=60)


class Conclusion(Strict):
    who: int | None = None
    how: int | None = None
    why: int | None = None


class CommandBody(Strict):
    request_id: str = Field(pattern=REQUEST_ID)
    revision: int = Field(ge=0)
    text: str | None = Field(None, max_length=200)
    do: str | None = Field(None, min_length=1, max_length=20)
    read: list[int] | None = Field(None, min_length=1, max_length=500)
    conclude: Conclusion | None = None

    @field_validator("text")
    @classmethod
    def strip_text(cls, value):
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def check_one(self):
        given = [self.do is not None or self.text is not None, self.read is not None, self.conclude is not None]
        if sum(given) != 1:
            raise ValueError("send one of text, do, read and conclude")
        return self


router = APIRouter(dependencies=[Depends(authenticate)])


@router.get("/stories")
def list_stories(request: Request):
    return request.app.state.service.list_stories()


@router.post("/games")
def create_game(request: Request, body: CreateBody):
    game, view = request.app.state.service.create(body.request_id, body.story)
    return {"game": game, "view": view}


@router.get("/games/{game}")
def show_game(request: Request, game: str):
    return request.app.state.service.show(game)


@router.get("/games/{game}/turns")
def list_turns(request: Request, game: str, start: Annotated[int, Query(alias="from", ge=1)] = 1):
    return request.app.state.service.list_turns(game, start)


@router.post("/games/{game}/commands")
async def run_command(request: Request, game: str, body: CommandBody):
    return await request.app.state.service.command(game, body.model_dump(exclude_none=True))


@router.get("/games/{game}/turns/{n}/text")
def stream_text(request: Request, game: str, n: int):
    events = request.app.state.service.stream_text(game, n)
    lines = (json.dumps(event, ensure_ascii=False) + "\n" async for event in events)
    return StreamingResponse(lines, media_type="application/x-ndjson")


@router.get("/games/{game}/turns/{n}/text/poll")
async def poll_text(request: Request, game: str, n: int, after: Annotated[int, Query(ge=0)] = 0):
    return await request.app.state.service.poll_text(game, n, after)
