"""LLM ad-hoc enemy summoning.

Calls the `summon` LLM to produce one character that obeys the pair-trade
invariant and registers it into GameState.characters. Caller: recovery's
sleep_encounters fallback when the seed pool is empty (P3 §2.4)."""

from __future__ import annotations

from src.llm.context.layers import build_world_layer
from ..domain.entities import Character, CombatBehavior, Location, Stats
from src.llm.calls.summon import (
    EncounterSummonInput,
    EncounterSummonOutput,
    summon,
)
from src.llm.client import LLMClient
from ..domain.state import GameState
from ..engines.growth import calc_max_hp, calc_max_mp
from ..engines.invariants import InvariantViolation, check_character
from src.db.repo import ScenarioRepo


async def _build_input(
    state: GameState,
    location: Location,
    scenario_repo: ScenarioRepo,
    profile: str,
    requested_role: str | None,
) -> EncounterSummonInput:
    world_text = await build_world_layer(scenario_repo, profile, missing_ok=True)
    races = [
        {"id": r.id, "name": r.name, "description": r.description}
        for r in state.races.values()
    ]
    player = state.characters.get(state.player_id)
    player_level = player.level if player else 1
    return EncounterSummonInput(
        world=world_text,
        location={
            "id": location.id,
            "name": location.name,
            "description": location.description,
            "tags": location.tags,
            "weather": location.weather,
            "sleep_risk": location.sleep_risk,
        },
        player_level=player_level,
        available_races=races,
        requested_role=requested_role,
    )


def _unique_character_id(state: GameState, base: str) -> str:
    """`<base>_NN` two-digit suffix not already in state.characters."""
    n = 1
    while f"{base}_{n:02d}" in state.characters:
        n += 1
    return f"{base}_{n:02d}"


def _make_character(
    state: GameState,
    out: EncounterSummonOutput,
    location_id: str,
) -> Character:
    cid = _unique_character_id(state, f"summoned_{out.race_id}")
    stats = Stats(
        STR=out.stats.STR,
        DEX=out.stats.DEX,
        CON=out.stats.CON,
        INT=out.stats.INT,
        WIS=out.stats.WIS,
        CHA=out.stats.CHA,
    )
    level = 0
    max_hp = calc_max_hp(level, stats.CON)
    max_mp = calc_max_mp(level, stats.INT)
    return Character(
        id=cid,
        name=out.name,
        description=out.description,
        appearance=out.appearance,
        tone_hint=out.tone_hint,
        race_id=out.race_id,
        gender=out.gender,
        location_id=location_id,
        stats=stats,
        level=level,
        hp=max_hp,
        max_hp=max_hp,
        mp=max_mp,
        max_mp=max_mp,
        combat_behavior=CombatBehavior(attack_priority=out.attack_priority),
    )


async def summon_encounter(
    client: LLMClient,
    state: GameState,
    location: Location,
    scenario_repo: ScenarioRepo,
    profile: str,
    *,
    dirty: set[tuple[str, str]] | None = None,
    requested_role: str | None = None,
) -> Character | None:
    """Summon one enemy via LLM and register it. Returns None if race_id is not in available races."""
    input_ = await _build_input(state, location, scenario_repo, profile, requested_role)
    out = await summon(client, input_, state.locale)
    if out.race_id not in state.races:
        return None
    char = _make_character(state, out, location.id)
    violations = check_character(char)
    if violations:
        raise InvariantViolation(
            "summoned character invariant violation:\n" + "\n".join(violations)
        )
    state.characters[char.id] = char
    if dirty is not None:
        dirty.add(("characters", char.id))
    return char
