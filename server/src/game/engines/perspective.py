"""Entity perspective (hints) update on engine events."""

from ...locale import render


def append_death_to_hints(entity, killer_name: str | None = None) -> None:
    """Idempotent: append death fact to entity.hints unless already present.
    The 'marker' catalog entries must be substrings of their hint counterparts so
    the dedupe check survives translations of the longer line."""
    if killer_name:
        marker = render("log.death.killed_marker", "ko")
        hint = render("log.death.killed", "ko", killer=killer_name)
    else:
        marker = render("log.death.died_marker", "ko")
        hint = render("log.death.died", "ko")
    if any(marker in h for h in entity.hints):
        return
    entity.hints.append(hint)
