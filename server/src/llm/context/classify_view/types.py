from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClassifyContextLimits:
    recent_scene: int = 3
    # Recent player input + narrator reply pairs used for pronoun/context resolution.
    recent_exchanges: int = 3
