"""Long rest at the current location.

No passive recovery — HP/MP heal only by sleeping (docs/03-features.md §2.4).
attempt_rest splits encounter vs full recovery via a risk roll. Full recovery restores
HP/MP to max and advances world_time by sleep_hours. On encounter it returns enemy_ids;
the caller (turn.py) is responsible for booting combat.

If the seeded sleep_encounters pool is empty and an LLM summon callback is supplied, an
ad-hoc enemy is summoned (P3 §2.4 fallback).
"""

import random
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Literal

from ..rules import RULES
from ..domain.state import GameState

SummonCallable = Callable[[GameState, str], Awaitable[str | None]]
"""(state, location_id) → registered character_id or None. None falls back to full recovery."""


def _advance_sleep(state: GameState) -> None:
    dt = datetime.fromisoformat(state.world_time)
    dt += timedelta(hours=RULES.time.sleep_hours)
    state.world_time = dt.isoformat()


def _full_recover(
    state: GameState,
    actor_id: str,
    dirty: set[tuple[str, str]] | None,
) -> None:
    actor = state.characters[actor_id]
    actor.hp = actor.max_hp
    actor.mp = actor.max_mp
    if dirty is not None:
        dirty.add(("characters", actor_id))


async def attempt_rest(
    state: GameState,
    actor_id: str,
    *,
    rng: random.Random | None = None,
    dirty: set[tuple[str, str]] | None = None,
    summon: SummonCallable | None = None,
) -> tuple[Literal["full_recovery", "encounter"], list[str]]:
    """Resolve encounter vs full recovery via a risk roll.

    When the encounter triggers and the sleep_encounters pool is empty, attempt an
    LLM-summoned enemy via the `summon` callback. summon=None or failure falls back to
    full recovery — a peaceful night that nothing wakes you from.
    On encounter return, every enemy_id is already registered in state.characters.
    """
    rng_obj = rng or random
    actor = state.characters[actor_id]
    if actor.location_id is None:
        # Stateless character — just full recovery and a time jump.
        _advance_sleep(state)
        _full_recover(state, actor_id, dirty)
        return "full_recovery", []

    location = state.locations.get(actor.location_id)
    risk = "safe" if location is None else location.sleep_risk
    chance = RULES.recovery.encounter_chance.get(risk, 0.0)

    if chance > 0 and rng_obj.random() < chance:
        pool: list[str] = []
        if location is not None:
            pool = [
                eid
                for eid in location.sleep_encounters
                if eid in state.characters and state.characters[eid].alive
            ]
        if pool:
            # Ambush right before sleep — time does not advance here (combat handles its own time).
            return "encounter", pool
        if summon is not None and location is not None:
            try:
                summoned_id = await summon(state, location.id)
            except Exception:
                summoned_id = None
            if summoned_id is not None:
                return "encounter", [summoned_id]

    _advance_sleep(state)
    _full_recover(state, actor_id, dirty)
    return "full_recovery", []
