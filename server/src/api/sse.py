import json
import logging
from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse

from ..flow.error_phrases import humanize_runtime_error

_log = logging.getLogger(__name__)


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
        # Log the raw exception for debugging; ship a sanitized Korean
        # message to the player. Upstream API JSON / English traces never
        # reach the client.
        _log.exception("SSE stream raised: %s", e)
        err = {
            "type": "error",
            "data": {
                "message": humanize_runtime_error(e),
                "code": type(e).__name__,
            },
        }
        yield sse_pack(err).encode("utf-8")


def streaming_response(events: AsyncIterator[dict]) -> StreamingResponse:
    return StreamingResponse(_wrap(events), media_type="text/event-stream")
