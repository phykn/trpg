from typing import Literal

from .hero import _CamelModel

__all__ = [
    "PlacePayload",
    "PlaceSurrounding",
    "PlaceTarget",
    "RiskBadge",
]


class RiskBadge(_CamelModel):
    """Sleep-risk visual atom: localized label + tone hint. Tone is the
    3-literal subset (`good`/`neutral`/`bad`) that wire.labels._RISK_TONES
    actually emits — domain `EncounterRisk` is a closed 3-value Literal so
    no fallback default ever fires. Sub-set of client `Tone` (9-literal),
    so client assignment is safe."""

    label: str
    tone: Literal["good", "neutral", "bad"]


class PlaceSurrounding(_CamelModel):
    """Adjacent navigable location, surfaced in the place panel.
    `difficulty` is the localized tier label (already rendered) or None
    when the connection has no tier requirement."""

    name: str
    blurb: str
    difficulty: str | None = None
    risk: RiskBadge


class PlaceTarget(_CamelModel):
    """Other inhabitants in the same location, visible to the player.
    `blurb` is appearance-or-description for living NPCs, `"죽음"` for the dead."""

    name: str
    level: int
    race_job: str
    gender: str
    blurb: str
    trust: int


class PlacePayload(_CamelModel):
    """Wire shape for the `place` slot inside the `state` payload.
    Field order matches wire/to_front.to_place's dict insertion order."""

    name: str
    description: str
    day_phase: str
    weather: list[str]
    features: list[str]
    surroundings: list[PlaceSurrounding]
    targets: list[PlaceTarget]
    risk: RiskBadge
