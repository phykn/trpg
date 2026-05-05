import json
import logging
from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse

from ..wire.emit import emit_error

_log = logging.getLogger(__name__)


def sse_pack(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


async def _wrap(events: AsyncIterator[dict]) -> AsyncIterator[bytes]:
    """SSE bytes generator. Wraps unhandled exceptions as `error` events; does NOT auto-append `done`."""
    try:
        async for ev in events:
            # Drop private inter-flow signals (type starts with "_") at the network boundary.
            if (
                isinstance(ev, dict)
                and isinstance(ev.get("type"), str)
                and ev["type"].startswith("_")
            ):
                continue
            yield sse_pack(ev).encode("utf-8")
    except Exception as e:
        # Sanitize before send: raw exceptions / English traces must never reach the player.
        _log.exception("SSE stream raised: %s", e)
        yield sse_pack(emit_error(e)).encode("utf-8")


def streaming_response(events: AsyncIterator[dict]) -> StreamingResponse:
    return StreamingResponse(_wrap(events), media_type="text/event-stream")
