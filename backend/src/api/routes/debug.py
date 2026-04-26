"""Debug-only LLM passthrough."""
from fastapi import APIRouter, Depends

from ...llm.client import LLMClient
from ..deps import get_llm
from ..schema import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/debug/complete", response_model=ChatResponse)
async def debug_complete(
    body: ChatRequest,
    llm: LLMClient = Depends(get_llm),
) -> ChatResponse:
    result = await llm.complete(body.system, body.query, body.think)
    return ChatResponse(**result)
