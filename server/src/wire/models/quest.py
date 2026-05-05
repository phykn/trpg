from typing import Literal

from .hero import _CamelModel

__all__ = ["DifficultyBadge", "QuestPayload", "QuestRewards"]


class DifficultyBadge(_CamelModel):
    """Difficulty visual atom for the quest panel: localized label + tone hint
    (the latter aligns with client `Tone` design-system literals; the 5-value
    subset matches wire.labels._TIER_TONE)."""

    label: str
    tone: Literal["neutral", "good", "exp", "accent", "bad"] | None = None


class QuestRewards(_CamelModel):
    """Wire view of quest rewards — gold + exp only. Domain QuestRewards also
    carries `items: list[str]` but the quest panel doesn't surface them today."""

    gold: int
    exp: int


class QuestPayload(_CamelModel):
    """Wire shape for the `quest` slot inside the `state` payload.
    Field order matches wire/to_front.to_quest's dict insertion order.
    `status` / `actions` are narrowed to the four/two literals to_quest can
    emit — domain Quest.status carries `locked`/`abandoned` too but those
    never reach the active-quest path."""

    id: str
    title: str
    summary: str
    giver: str
    difficulty: DifficultyBadge
    goals: list[str]
    progress_label: str
    conditions: list[str]
    rewards: QuestRewards
    status: Literal["pending", "active", "completed", "failed"]
    actions: list[Literal["accept", "abandon"]]
