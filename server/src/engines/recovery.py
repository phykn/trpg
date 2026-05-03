"""Long rest at the current location. attempt_rest rolls risk vs full recovery; on full recovery it restores HP/MP and jumps turn_count to the next 새벽 boundary."""

import random
from collections.abc import Awaitable, Callable
from typing import Literal

from pydantic import ValidationError

from ..domain.clock import next_dawn_turn
from ..domain.errors import LLMUnavailable
from ..domain.state import GameState
from ..rules import RULES

SummonCallable = Callable[[GameState, str], Awaitable[str | None]]
"""(state, location_id) → registered character_id or None. None falls back to full recovery."""


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

    def full_recover() -> None:
        # Defensive: the upstream /turn flow already blocks dead players from resting,
        # but the engine shouldn't trust that — a dead actor with hp == max_hp would
        # break the alive=False/hp>0 invariant.
        if not actor.alive:
            return
        state.turn_count = next_dawn_turn(state.turn_count)
        actor.hp = actor.max_hp
        actor.mp = actor.max_mp
        if dirty is not None:
            dirty.add(("characters", actor_id))

    if actor.location_id is None:
        full_recover()
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
            # ValidationError = LLM produced bad output even after 5 retries.
            # LLMUnavailable = transport wrap from agents/_runner.py.
            # OSError/TimeoutError = bare transport failure (e.g. narrate stream).
            # Programming bugs (TypeError, AttributeError, ...) propagate so they don't hide.
            try:
                summoned_id = await summon(state, location.id)
            except (ValidationError, LLMUnavailable, OSError, TimeoutError):
                summoned_id = None
            if summoned_id is not None:
                return "encounter", [summoned_id]

    full_recover()
    return "full_recovery", []
