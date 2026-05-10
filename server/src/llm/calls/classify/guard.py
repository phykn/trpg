from src.game.domain.action import ActionOutput, RefuseReason
from src.locale.render import render


_META_BREAKING_TERMS = (
    "\uc2dc\uc2a4\ud15c \ud504\ub86c\ud504\ud2b8",
    "\ud504\ub86c\ud504\ud2b8 \uc6d0\ubb38",
    "\uc774\uc804 \uc9c0\uc2dc\ub97c \ubb34\uc2dc",
    "ignore previous",
    "system prompt",
)
_REAL_WORLD_TERMS = ("\ud604\uc2e4", "\uc2e4\uc81c", "real world")
_WEATHER_TERM = "\ub0a0\uc528"


def classify_guard(player_input: str, *, locale: str = "ko") -> ActionOutput | None:
    lowered = player_input.lower()
    if any(term.lower() in lowered for term in _META_BREAKING_TERMS):
        return ActionOutput(
            refuse=RefuseReason(
                category="meta_breaking",
                message_hint=render(
                    "runtime.classify.refuse_meta_breaking",
                    locale,
                ),
            )
        )
    if _WEATHER_TERM in player_input and any(
        term.lower() in lowered for term in _REAL_WORLD_TERMS
    ):
        return ActionOutput(
            refuse=RefuseReason(
                category="out_of_game",
                message_hint=render(
                    "runtime.classify.refuse_out_of_game",
                    locale,
                ),
            )
        )
    return None
