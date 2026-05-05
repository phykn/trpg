"""Debug-only LLM passthrough."""

from pathlib import Path

from fastapi import APIRouter, Depends

from src.llm.client import LLMClient
from ..deps import get_llm
from ..schema import ChatRequest, ChatResponse

router = APIRouter()


def _resolve_system(system: str | None) -> str | None:
    if system is None:
        return None
    s = system.strip()
    if s.endswith(".md") and Path(s).is_file():
        return Path(s).read_text(encoding="utf-8")
    return system


@router.post("/debug/complete", response_model=ChatResponse)
async def debug_complete(
    body: ChatRequest,
    llm: LLMClient = Depends(get_llm),
) -> ChatResponse:
    messages: list[dict] = []
    sys_text = _resolve_system(body.system)
    if sys_text:
        messages.append({"role": "system", "content": sys_text})
    messages.append({"role": "user", "content": body.query})
    result = await llm.chat(messages, think=body.think)
    return ChatResponse(**result)
