from src.game.domain.types import Tier
from src.locale import render


_TIER_TONE: dict[Tier, str | None] = {
    "very_easy": "neutral",
    "easy": "good",
    "normal": None,
    "hard": "exp",
    "very_hard": "accent",
    "legend": "bad",
    "myth": "bad",
}


def difficulty_badge(tier: str) -> dict:
    return {"label": render(f"tier.{tier}", "ko"), "tone": _TIER_TONE.get(tier)}
