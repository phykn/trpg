from src.game.domain.action import ActionOutput, RefuseReason
from src.locale.lexicon import (
    META_BREAKING_TERMS,
    REAL_WORLD_TERMS,
    WEATHER_TERM,
)
from src.locale.render import render


def classify_guard(player_input: str, *, locale: str = "ko") -> ActionOutput | None:
    lowered = player_input.lower()
    if any(term.lower() in lowered for term in META_BREAKING_TERMS):
        return ActionOutput(
            refuse=RefuseReason(
                category="meta_breaking",
                message_hint=render(
                    "runtime.classify.refuse_meta_breaking",
                    locale,
                ),
            )
        )
    if WEATHER_TERM in player_input and any(
        term.lower() in lowered for term in REAL_WORLD_TERMS
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
