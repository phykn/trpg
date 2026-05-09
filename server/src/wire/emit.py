import re
from typing import TYPE_CHECKING, Literal

from src.locale import render
from .models import (
    CombatEndPayload,
    CombatStartPayload,
    CombatTurnPayload,
    DonePayload,
    ErrorPayload,
    JudgePayload,
    JudgeRefuse,
    JudgeVerb,
    JudgeVerbs,
    LogEntryPayload,
    NarrativeDeltaPayload,
    PendingCheckPayload,
    PendingConfirmationPayload,
    SuggestionsPayload,
    TierBadge,
)

if TYPE_CHECKING:
    from src.game.domain.memory import PendingCheck
    from src.game.domain.state import GameState
    from src.game.domain.verb import RefuseReason, Verb

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
    wire.pending_check_to_front share one source of truth."""
    from src.game.domain.types import tier_to_int
    from .labels import stat_label

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


def emit_confirmation_required(pending: dict[str, object]) -> dict:
    payload = PendingConfirmationPayload.model_validate(_confirmation_wire(pending))
    return {"type": "confirmation_required", "data": payload.model_dump()}


def _confirmation_wire(pending: dict[str, object]) -> dict[str, object]:
    return {
        key: pending[key]
        for key in (
            "id",
            "kind",
            "title",
            "body",
            "confirm_label",
            "cancel_label",
            "target_label",
        )
        if key in pending
    }


def emit_judge_refuse(refuse: "RefuseReason") -> dict:
    """SSE judge event — refuse branch."""
    payload = JudgePayload(root=JudgeRefuse(judge_kind="refuse", refuse=refuse))
    return {"type": "judge", "data": payload.model_dump()}


def emit_judge_verb(verb: "Verb") -> dict:
    """SSE judge event — single-verb branch."""
    payload = JudgePayload(root=JudgeVerb(judge_kind="verb", verb=verb))
    return {"type": "judge", "data": payload.model_dump()}


def emit_judge_verbs(actions: list["Verb"]) -> dict:
    """SSE judge event — multi-verb chain branch."""
    payload = JudgePayload(root=JudgeVerbs(judge_kind="verbs", actions=list(actions)))
    return {"type": "judge", "data": payload.model_dump()}


def emit_log_entry(log) -> dict:
    """SSE log_entry event. Wraps a GMLogEntry / PlayerLogEntry /
    ActLogEntry / RollLogEntry instance. Caller passes the already-built
    domain log object; the discriminated-union validator rejects anything
    else with ValidationError (loud-fail consistent with other builders)."""
    payload = LogEntryPayload(root=log)
    return {"type": "log_entry", "data": payload.model_dump()}


def emit_narrative_delta(text: str) -> dict:
    """SSE narrative_delta event. Streams a prose chunk to the client."""
    payload = NarrativeDeltaPayload(text=text)
    return {"type": "narrative_delta", "data": payload.model_dump()}


def emit_suggestions(items: list[str]) -> dict:
    """SSE suggestions event. Defensive list copy."""
    payload = SuggestionsPayload(items=list(items))
    return {"type": "suggestions", "data": payload.model_dump()}


def emit_done() -> dict:
    """SSE done event. Empty payload — turn-end marker."""
    payload = DonePayload()
    return {"type": "done", "data": payload.model_dump()}


def emit_combat_start(
    *,
    turn_order: list[str],
    round: int,
    surprise: Literal["player", "enemy"] | None,
    enemy_ids: list[str],
) -> dict:
    """SSE combat_start event. Defensive list copies for turn_order/enemy_ids."""
    payload = CombatStartPayload(
        turn_order=list(turn_order),
        round=round,
        surprise=surprise,
        enemy_ids=list(enemy_ids),
    )
    return {"type": "combat_start", "data": payload.model_dump()}


def emit_combat_turn(payload: "CombatTurnPayload | dict") -> dict:
    """SSE combat_turn event. Accepts either a CombatTurnPayload instance or
    a raw dict (auto-combat emits dicts via _turn_event factory). Dict input
    is validated against CombatTurnPayload — loud-fail on shape mismatch."""
    if not isinstance(payload, CombatTurnPayload):
        payload = CombatTurnPayload.model_validate(payload)
    return {"type": "combat_turn", "data": payload.model_dump()}


def emit_combat_end(
    outcome: Literal["victory", "defeat", "downed", "fled"],
) -> dict:
    """SSE combat_end event."""
    payload = CombatEndPayload(outcome=outcome)
    return {"type": "combat_end", "data": payload.model_dump()}
