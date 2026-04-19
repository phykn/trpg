import json

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from starlette.concurrency import iterate_in_threadpool

from .schema import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/complete", response_model=ChatResponse)
async def complete(request: Request, body: ChatRequest) -> ChatResponse:
    async with request.app.state.chat_sem:
        result = await run_in_threadpool(
            request.app.state.llm.complete, body.system, body.query, body.think
        )
    return ChatResponse(**result)


@router.post("/stream")
async def stream(request: Request, body: ChatRequest) -> StreamingResponse:
    async def event_source():
        async with request.app.state.chat_sem:
            sync_iter = request.app.state.llm.stream(
                body.system, body.query, body.think
            )
            async for chunk in iterate_in_threadpool(sync_iter):
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")
