from pydantic import BaseModel

__all__ = ["SuggestionsPayload"]


class SuggestionsPayload(BaseModel):
    """SSE suggestions event payload — short ordered list of clickable
    follow-up actions for the player. Items are localized strings."""

    items: list[str]
