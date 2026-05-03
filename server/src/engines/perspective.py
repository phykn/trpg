"""Entity perspective (hints) update on engine events."""


def append_death_to_hints(entity, killer_name: str | None = None) -> None:
    """Idempotent: append death fact to entity.hints unless already present."""
    death_marker = "살해당했다" if killer_name else "사망했다"
    if any(death_marker in h for h in entity.hints):
        return
    if killer_name:
        entity.hints.append(f"{killer_name}에게 살해당했다.")
    else:
        entity.hints.append("사망했다.")
