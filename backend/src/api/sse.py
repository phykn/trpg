import json
from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse


def sse_pack(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


async def _wrap(events: AsyncIterator[dict]) -> AsyncIterator[bytes]:
    """SSE bytes generator. Wraps unhandled exceptions as `error` events.

    Does NOT auto-append `done` — some flows (pending_check) intentionally end
    without one and the client treats stream-close as the signal.
    """
    try:
        async for ev in events:
            yield sse_pack(ev).encode("utf-8")
    except Exception as e:
        err = {"type": "error", "data": {"message": str(e), "code": type(e).__name__}}
        yield sse_pack(err).encode("utf-8")


def streaming_response(events: AsyncIterator[dict]) -> StreamingResponse:
    return StreamingResponse(_wrap(events), media_type="text/event-stream")
