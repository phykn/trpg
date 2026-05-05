import re
from typing import TYPE_CHECKING

from ..locale import render
from .models import ErrorPayload, PendingCheckPayload, TierBadge

if TYPE_CHECKING:
    from ..domain.memory import PendingCheck
    from ..domain.state import GameState

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _to_snake(name: str) -> str:
    return _CAMEL_BOUNDARY.sub("_", name).lower()


def emit_error(
    code_or_exc: str | Exception,
    *,
    locale: str = "ko",
    message: str | None = None,
    **vars: object,
) -> dict:
    """SSE error event.

    - `code_or_exc` is an Exception (uses class name as code) or a string code.
    - `message` overrides catalog lookup when provided.
    - `**vars` pass to render() for catalog template interpolation.
    - Catalog miss without explicit message falls back to error.runtime_generic.
    """
    if isinstance(code_or_exc, Exception):
        code = type(code_or_exc).__name__
    else:
        code = code_or_exc

    if message is None:
        key = f"error.{_to_snake(code)}"
        try:
            message = render(key, locale, **vars)
        except KeyError:
            message = render("error.runtime_generic", locale)

    payload = ErrorPayload(code=code, message=message)
    return {"type": "error", "data": payload.model_dump()}


def _build_pending_check_payload(
    state: "GameState", pending: "PendingCheck"
) -> PendingCheckPayload:
    """Build the wire model from domain state. Centralizes derivation
    (stat_label, stat_value, tier badge) so both emit_pending_check and
    mapping.pending_check_to_front share one source of truth."""
    from ..domain.types import tier_to_int
    from ..mapping.labels import stat_label

    actor = state.characters[state.player_id]
    return PendingCheckPayload(
        kind=pending.kind,
        dc=pending.dc,
        stat=pending.stat,
        stat_label=stat_label(pending.stat),
        stat_value=getattr(actor.stats, pending.stat),
        mod=pending.mod,
        required_roll=pending.required_roll,
        tier=TierBadge(
            value=tier_to_int(pending.tier),
            max=7,
            label=render(f"tier.{pending.tier}", "ko"),
        ),
        target=pending.target,
        reason=pending.reason,
    )


def emit_pending_check(state: "GameState", pending: "PendingCheck") -> dict:
    """SSE pending_check event. Mirrors emit_error pattern: state + pending →
    full {"type": "pending_check", "data": {...}} envelope."""
    payload = _build_pending_check_payload(state, pending)
    return {"type": "pending_check", "data": payload.model_dump()}
