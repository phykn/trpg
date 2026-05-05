from pydantic import BaseModel

__all__ = ["DonePayload"]


class DonePayload(BaseModel):
    """SSE done event payload — turn ended marker. Empty body; client
    treats stream-close as the signal but the explicit event is also
    emitted by `dirty.run` after suggestions."""
