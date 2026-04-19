import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ..llm_client.agents import JudgeInput, JudgeOutput, judge
from .schema import ChatRequest, ChatResponse

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


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


@router.post("/agents/judge")
async def agents_judge(request: Request, body: JudgeInput) -> JudgeOutput:
    return await judge(request.app.state.llm, body)
