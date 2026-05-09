from typing import Annotated, Literal

from pydantic import BaseModel, Field, RootModel

from src.game.domain.verb import RefuseReason, Verb

__all__ = [
    "JudgePayload",
    "JudgeRefuse",
    "JudgeVerb",
    "JudgeVerbs",
]


class JudgeRefuse(BaseModel):
    """Player input rejected at the judge layer (out_of_game / meta_breaking)."""

    judge_kind: Literal["refuse"]
    refuse: RefuseReason


class JudgeVerb(BaseModel):
    """Single verb classification — most common branch."""

    judge_kind: Literal["verb"]
    verb: Verb


class JudgeVerbs(BaseModel):
    """Multi-verb chain (out-of-combat only). Field name is `actions` to
    match the existing wire shape consumed by the client."""

    judge_kind: Literal["verbs"]
    actions: list[Verb]


class JudgePayload(RootModel):
    """SSE `judge` event payload — discriminated union over `judge_kind`.
    RootModel is the Pydantic v2 way to wrap a non-class root type so it can
    be exported alongside other top-level wire models in wire/export.py."""

    root: Annotated[
        JudgeRefuse | JudgeVerb | JudgeVerbs,
        Field(discriminator="judge_kind"),
    ]
