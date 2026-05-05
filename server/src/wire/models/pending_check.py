from typing import Literal

from pydantic import BaseModel


class TierBadge(BaseModel):
    """Difficulty tier display: numeric position (value/max) plus localized label."""

    value: int
    max: int
    label: str


class PendingCheckPayload(BaseModel):
    """Wire shape for the `pending_check` SSE event and the `pendingCheck` slot
    inside the `state` payload."""

    kind: Literal["stat", "recruit", "steal"]
    dc: int
    stat: str
    stat_label: str
    stat_value: int
    mod: int
    required_roll: int
    tier: TierBadge
    target: str
    reason: str
