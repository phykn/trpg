"""Persistence schema shared by both the LocalFs (`store.py`) and Supabase (`supabase.py`) adapters.

`_Meta` is the canonical meta-row shape — file payload for LocalFs, `games.meta` jsonb column for Supabase. `_ENTITY_MODELS` maps the entity-bucket name to its Pydantic class for round-trip validation."""

from pydantic import BaseModel

from src.game.domain.entities import (
    Campaign,
    Chapter,
    Character,
    Item,
    Location,
    Quest,
    Race,
    Skill,
)
from src.game.domain.memory import LogEntry, PendingCheck
from src.game.domain.state import CombatState, GameState


_ENTITY_MODELS: dict[str, type[BaseModel]] = {
    "characters": Character,
    "items": Item,
    "locations": Location,
    "races": Race,
    "skills": Skill,
    "quests": Quest,
    "chapters": Chapter,
    "campaigns": Campaign,
}


class _Meta(BaseModel):
    game_id: str
    profile: str
    locale: str = "ko"
    player_id: str
    active_subject_id: str | None = None
    active_quest_id: str | None = None
    turn_count: int = 0
    pending_check: PendingCheck | None = None
    combat_state: CombatState | None = None
    previous_phase_signal: str | None = None
    next_log_id: int = 1


def _meta_from_state(state: GameState) -> _Meta:
    return _Meta(
        game_id=state.game_id,
        profile=state.profile,
        locale=state.locale,
        player_id=state.player_id,
        active_subject_id=state.active_subject_id,
        active_quest_id=state.active_quest_id,
        turn_count=state.turn_count,
        pending_check=state.pending_check,
        combat_state=state.combat_state,
        previous_phase_signal=state.previous_phase_signal,
        next_log_id=state.next_log_id,
    )


def _resolve_next_log_id(meta_next_log_id: int, log_entries: list[LogEntry]) -> int:
    """A mid-flush crash can leave meta stale while log rows already carry new
    entries. Bumping past the largest id actually loaded prevents id collisions
    on the next turn."""
    if not log_entries:
        return meta_next_log_id
    return max(meta_next_log_id, max(e.id for e in log_entries) + 1)
