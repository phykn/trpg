from src.game.domain.action import ActionOutput, RefuseReason
from src.locale.render import render
from src.locale.terms import META_BREAKING_TERMS


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
    return None
