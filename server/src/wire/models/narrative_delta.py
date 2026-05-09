from pydantic import BaseModel

__all__ = ["NarrativeDeltaPayload"]


class NarrativeDeltaPayload(BaseModel):
    """SSE narrative_delta event payload — incremental prose chunk streamed
    from narrate / combat_narrate. Concatenated client-side until the body
    is complete."""

    text: str
