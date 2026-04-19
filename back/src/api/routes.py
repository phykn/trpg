import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .schema import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/complete", response_model=ChatResponse)
async def complete(request: Request, body: ChatRequest) -> ChatResponse:
    result = await request.app.state.llm.complete(body.system, body.query, body.think)
    return ChatResponse(**result)


@router.post("/stream")
async def stream(request: Request, body: ChatRequest) -> StreamingResponse:
    async def event_source():
        async for chunk in request.app.state.llm.stream(
            body.system, body.query, body.think
        ):
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")
