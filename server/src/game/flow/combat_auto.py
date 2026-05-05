"""Auto-combat sim — runs the entire fight (or up to round cap) deterministically,
mutates GameState, and produces the trace plus snapshots that the caller hands
to combat_narrate for one cinematic body and to format_combat_outcome_summary for the
numeric act-line that follows."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from ...llm.calls.combat_narrate.schema import (
    CombatNarrateInput,
    CombatOutcome,
    CombatRoundEvent,
    EnemyEndSnapshot,
    EnemyStartSnapshot,
    PlayerNarrateSnapshot,
)
from ...llm.context.layers import build_world_layer
from ..domain.entities import Character
from ..domain.errors import SkillInvalid
from ..domain.state import GameState
from ..engines import combat as combat_engine
from ..ontology.player_view import build_player_view
from ..ontology.queries import location_of, race_of
from ...persistence.repo import ScenarioRepo
from ..rules import RULES
from .actions import apply_attack_action, apply_skill_action
from .buff_tick import tick_turn_buffs
from .dirty import Dirty, register_kill

# Safety belt against pathological stalemates — hitting it resolves the cycle as `fled`.
HARD_CAP = 50


@dataclass
class PlayerAction:
    """Per-round player action. kind ∈ {'attack', 'skill', 'pass', 'flee'}."""

    kind: str
    skill_id: str | None = None
    targets: list[str] = field(default_factory=list)


@dataclass
class EnemyHit:
    id: str
    name: str
    damage_total: int
    hp_after: int
    max_hp: int
    killed: bool


@dataclass
class AutoCombatResult:
    events: list[CombatRoundEvent]
    turn_events: list[dict] = field(default_factory=list)
    rounds_run: int = 0
    outcome: CombatOutcome = "fled"
    enemy_hits: list[EnemyHit] = field(default_factory=list)
    player_damage_total: int = 0
    player_revived: bool = False
    player_revive_coins_after: int = 0
    player_revive_coins_max: int = 0
    player_hp_before: int = 0
    player_hp_after: int = 0
    player_max_hp: int = 0
    enemy_starts: list[EnemyStartSnapshot] = field(default_factory=list)
    player_start: PlayerNarrateSnapshot | None = None
    player_name: str = (
        ""  # used by format.py for log lines; name not carried on PlayerNarrateSnapshot
    )
    # True iff this fight opened with the player ambushing the enemy (round 1 enemy skip).
    player_surprise: bool = False


def _turn_event(
    actor_id: str,
    action: str,
    *,
    target_id: str | None = None,
    grade: str | None = None,
    damage: int = 0,
    killed: bool = False,
    skill_name: str | None = None,
    skill_id: str | None = None,
    round_no: int,
) -> dict:
    """SSE payload for one combat action; keys actors by id (the cinematic event keys by name)."""
    return {
        "actor": actor_id,
        "action": action,
        "grade": grade,
        "damage": damage,
        "killed": killed,
        "target": target_id,
        "skill_name": skill_name,
        "skill_id": skill_id,
        "round": round_no,
    }


def _emit_round_event(
    events: list[CombatRoundEvent],
    turn_events: list[dict],
    *,
    actor: Character,
    action_label: str,
    round_no: int,
    target_id: str | None = None,
    target_name: str | None = None,
    grade: str | None = None,
    damage: int = 0,
    killed: bool = False,
    skill_name: str | None = None,
    skill_id: str | None = None,
) -> None:
    events.append(
        CombatRoundEvent(
            round_no=round_no,
            actor=actor.name,
            action=action_label,
            target=target_name,
            grade=grade,
            killed=killed,
            skill_name=skill_name,
        )
    )
    turn_events.append(
        _turn_event(
            actor.id,
            action_label,
            target_id=target_id,
            grade=grade,
            damage=damage,
            killed=killed,
            skill_name=skill_name,
            skill_id=skill_id,
            round_no=round_no,
        )
    )


def _enemy_start_snapshot(state: GameState, enemy_id: str) -> EnemyStartSnapshot:
    c = state.characters[enemy_id]
    race_id = race_of(state.graph(), enemy_id)
    race = state.races.get(race_id) if race_id else None
    race_payload: dict | None = None
    if race is not None:
        race_payload = {"name": race.name}
        if race.description:
            race_payload["description"] = race.description
    return EnemyStartSnapshot(
        name=c.name,
        alive=c.alive,
        race=race_payload,
        appearance=c.appearance or None,
        description=c.description or None,
        gender=c.gender if c.gender != "none" else None,
    )


def _enemy_end_snapshot(state: GameState, enemy_id: str) -> EnemyEndSnapshot:
    c = state.characters[enemy_id]
    return EnemyEndSnapshot(name=c.name, alive=c.alive)


def _location_payload(state: GameState) -> dict:
    actor = state.characters.get(state.player_id)
    if actor is None:
        return {}
    loc_id = location_of(state.graph(), state.player_id)
    if loc_id is None:
        return {}
    loc = state.locations.get(loc_id)
    if loc is None:
        return {}
    return {
        "id": loc.id,
        "name": loc.name,
        "description": loc.description,
        "tags": list(loc.tags),
        "weather": loc.weather,
    }


def _is_surprise_skip(state: GameState, actor_id: str) -> bool:
    cs = state.combat_state
    if cs is None or cs.round != 1 or cs.surprise is None:
        return False
    is_player = actor_id == state.player_id
    return (cs.surprise == "enemy" and is_player) or (
        cs.surprise == "player" and not is_player
    )


def _player_round_action(
    base: PlayerAction, round_no: int, player: Character, state: GameState
) -> PlayerAction:
    """Round 1 follows the player's input verbatim. Round 2+ keeps the same
    skill if MP/level allow; otherwise (or for pass/flee on round 2+) falls
    back to a basic attack against the same targets."""
    if round_no == 1:
        return base
    if base.kind == "skill" and base.skill_id:
        skill = state.skills.get(base.skill_id)
        if (
            skill is not None
            and player.mp >= skill.mp_cost
            and player.level >= skill.level
        ):
            return base
    return PlayerAction(kind="attack", targets=list(base.targets))


def _alive_player_targets(
    state: GameState, player: Character, requested: list[str]
) -> list[str]:
    """Filter requested targets to alive enemies in the player's location.
    Falls back to combat_state.enemy_ids when none of the requested are valid."""
    graph = state.graph()
    player_loc = location_of(graph, player.id)
    in_loc = [
        tid
        for tid in requested
        if tid in state.characters
        and state.characters[tid].alive
        and location_of(graph, tid) == player_loc
    ]
    if in_loc:
        return in_loc
    cs = state.combat_state
    if cs is None:
        return []
    return [
        eid
        for eid in cs.enemy_ids
        if eid in state.characters and state.characters[eid].alive
    ]


def _resolve_player_turn(
    state: GameState,
    player: Character,
    action: PlayerAction,
    round_no: int,
    dirty: Dirty,
    rng: random.Random,
) -> tuple[list[CombatRoundEvent], list[dict]]:
    events: list[CombatRoundEvent] = []
    turn_events: list[dict] = []
    targets = _alive_player_targets(state, player, action.targets)

    def _add(action_label: str, **kwargs):
        _emit_round_event(
            events,
            turn_events,
            actor=player,
            action_label=action_label,
            round_no=round_no,
            **kwargs,
        )

    if action.kind == "pass":
        _add("pass")
        return events, turn_events

    if action.kind == "flee":
        ok, _roll = combat_engine.try_flee(player, rng=rng)
        _add("flee", grade="success" if ok else "failure")
        if ok:
            combat_engine.remove_from_combat(state, player.id)
        return events, turn_events

    if not targets:
        _add("pass")
        return events, turn_events

    if action.kind == "skill" and action.skill_id:
        try:
            cast = apply_skill_action(
                state,
                player.id,
                action.skill_id,
                targets[:1],
                dirty,
                rng=rng,
            )
            for eff in cast["effects"]:
                tid = eff.get("target")
                target = state.characters.get(tid) if tid else None
                _add(
                    "skill",
                    target_id=tid,
                    target_name=target.name if target else None,
                    skill_name=cast["skill_name"],
                    skill_id=cast["skill_id"],
                    damage=int(eff.get("damage", 0)),
                    grade=cast["grade"],
                    killed=tid in cast["killed_ids"],
                )
            return events, turn_events
        except SkillInvalid:
            pass

    target_id = targets[0]
    target = state.characters[target_id]
    outcome = combat_engine.attack(player, target, state.items, rng=rng)
    apply_result = apply_attack_action(state, player.id, target_id, outcome, dirty)
    _add(
        "attack" if outcome.damage > 0 else "miss",
        target_id=target_id,
        target_name=target.name,
        damage=outcome.damage,
        grade=outcome.grade,
        killed=apply_result["killed"],
    )
    return events, turn_events


def _resolve_npc_turn(
    state: GameState,
    actor: Character,
    round_no: int,
    dirty: Dirty,
    rng: random.Random,
) -> tuple[list[CombatRoundEvent], list[dict]]:
    events: list[CombatRoundEvent] = []
    turn_events: list[dict] = []

    def _add(action_label: str, **kwargs):
        _emit_round_event(
            events,
            turn_events,
            actor=actor,
            action_label=action_label,
            round_no=round_no,
            **kwargs,
        )

    if combat_engine.should_attempt_flee(actor, rng=rng):
        ok, _ = combat_engine.try_flee(actor, rng=rng)
        _add("flee", grade="success" if ok else "failure")
        if ok:
            combat_engine.remove_from_combat(state, actor.id)
        return events, turn_events

    target = combat_engine.pick_npc_target(state, actor.id, rng=rng)
    if target is None:
        _add("pass")
        return events, turn_events
    outcome = combat_engine.attack(actor, target, state.items, rng=rng)
    apply_result = apply_attack_action(state, actor.id, target.id, outcome, dirty)
    _add(
        "attack" if outcome.damage > 0 else "miss",
        target_id=target.id,
        target_name=target.name,
        damage=outcome.damage,
        grade=outcome.grade,
        killed=apply_result["killed"],
    )
    return events, turn_events


def _auto_resolve_death_save(
    state: GameState,
    dirty: Dirty,
    rng: random.Random,
) -> str:
    """Roll death-saves until stable or dead. Returns 'stable' | 'dead'."""
    while True:
        status, _ = combat_engine.tick_death_save(
            state,
            state.player_id,
            rng=rng,
            dirty=dirty.entities,
        )
        if status == "stable":
            return "stable"
        if status == "dead":
            register_kill(state, state.player_id, dirty)
            return "dead"


def run_auto_combat(
    state: GameState,
    dirty: Dirty,
    *,
    player_action: PlayerAction,
    rng: random.Random | None = None,
    cap: int | None = None,
) -> AutoCombatResult:
    """Drive the fight to terminal outcome. cap=1 is the rest-ambush surprise round; default runs to victory/defeat/fled/downed under HARD_CAP."""
    r = rng or random
    cs = state.combat_state
    if cs is None:
        raise RuntimeError("run_auto_combat called without combat_state")

    player = state.characters[state.player_id]
    player_surprise = cs.surprise == "player"
    enemy_ids_at_start = list(cs.enemy_ids)
    enemy_starts = [
        _enemy_start_snapshot(state, eid)
        for eid in enemy_ids_at_start
        if eid in state.characters
    ]
    # Engine-side HP snapshot — the LLM payload omits hp to avoid numeric leak, so we track it here.
    enemy_starting_hp: dict[str, int] = {
        eid: state.characters[eid].hp
        for eid in enemy_ids_at_start
        if eid in state.characters
    }
    player_start = PlayerNarrateSnapshot(alive=player.alive)
    player_hp_before = player.hp
    player_revive_coins_before = player.revive_coins

    events: list[CombatRoundEvent] = []
    turn_events: list[dict] = []
    rounds_run = 0
    outcome: CombatOutcome = "fled"  # safety default if HARD_CAP fires
    outcome_decided = False
    player_fled = False
    effective_cap = cap if cap is not None else HARD_CAP

    for _ in range(effective_cap):
        if state.combat_state is None:
            break
        cur_round = state.combat_state.round
        rounds_run += 1
        order_snapshot = list(state.combat_state.turn_order)

        for actor_id in order_snapshot:
            if state.combat_state is None:
                break
            if actor_id not in state.combat_state.turn_order:
                continue
            actor = state.characters.get(actor_id)
            if actor is None or not actor.alive:
                continue

            if _is_surprise_skip(state, actor_id):
                events.append(
                    CombatRoundEvent(
                        round_no=cur_round,
                        actor=actor.name,
                        action="pass",
                    )
                )
                turn_events.append(
                    _turn_event(
                        actor_id,
                        "pass",
                        round_no=cur_round,
                    )
                )
                continue

            coins_before_action = player.revive_coins
            if actor_id == state.player_id:
                round_action = _player_round_action(
                    player_action, cur_round, player, state
                )
                evs, tevs = _resolve_player_turn(
                    state, player, round_action, cur_round, dirty, r
                )
                events.extend(evs)
                turn_events.extend(tevs)
                if (
                    state.combat_state is None
                    or state.player_id not in state.combat_state.turn_order
                ):
                    player_fled = True
                    break
            else:
                evs, tevs = _resolve_npc_turn(state, actor, cur_round, dirty, r)
                events.extend(evs)
                turn_events.extend(tevs)

            if not player.alive:
                break
            # Coin-revive ends the fight: player at auto_revive_hp, must recover before re-engaging.
            if player.revive_coins < coins_before_action:
                outcome = "downed"
                outcome_decided = True
                break
            if player.death_saves is not None:
                ds = _auto_resolve_death_save(state, dirty, r)
                if ds == "dead":
                    break
                outcome = "downed"
                outcome_decided = True
                break  # stable — fight ends here for this turn

            end = combat_engine.check_combat_end(state)
            if end is not None:
                break

        # End-of-round tick: buff durations are measured in combat rounds. Without this
        # a 5-round fight would still only burn one duration off, making `duration: 3`
        # behave like "lasts 3 separate fights" instead of "lasts 3 rounds". Placed
        # before the break checks so the terminating round also gets its tick.
        tick_turn_buffs(state, dirty)

        if player_fled:
            outcome = "fled"
            outcome_decided = True
            break
        if not player.alive:
            outcome = "defeat"
            outcome_decided = True
            break
        if outcome_decided:
            break
        end = combat_engine.check_combat_end(state)
        if end == "victory":
            outcome = "victory"
            outcome_decided = True
            break
        if end == "defeat":
            outcome = "defeat"
            outcome_decided = True
            break

        if state.combat_state is not None:
            state.combat_state.round += 1
            state.combat_state.current_turn = 0

    enemy_hits: list[EnemyHit] = []
    for eid in enemy_ids_at_start:
        ch = state.characters.get(eid)
        if ch is None:
            continue
        start_hp = enemy_starting_hp.get(eid, ch.hp)
        dmg = max(0, start_hp - ch.hp)
        enemy_hits.append(
            EnemyHit(
                id=eid,
                name=ch.name,
                damage_total=dmg,
                hp_after=ch.hp,
                max_hp=ch.max_hp,
                killed=not ch.alive,
            )
        )

    player_revived = (
        player_revive_coins_before > player.revive_coins or outcome == "downed"
    )
    # Raw damage = visible HP delta + the auto_revive_hp the engine handed back. Without the +auto_revive_hp,
    # a coin-revive turn reads "X 피해 (HP 1/Y)" where X is one short of what actually hit (HP went pre-hit→0→1).
    naive_damage = max(0, player_hp_before - player.hp)
    player_damage_total = (
        naive_damage + RULES.death.auto_revive_hp if player_revived else naive_damage
    )
    if player_revived:
        # One-shot signal so next turn's narrate opens with recovery prose; consumed and cleared in flow/turn.py.
        state.previous_phase_signal = "downed_recovered"

    # All terminal outcomes (including HARD_CAP `fled` fallback) clear combat_state here.
    combat_engine.end_combat(state)

    return AutoCombatResult(
        events=events,
        turn_events=turn_events,
        rounds_run=max(1, rounds_run),
        outcome=outcome,
        enemy_hits=enemy_hits,
        player_damage_total=player_damage_total,
        player_revived=player_revived,
        player_revive_coins_after=player.revive_coins,
        player_revive_coins_max=RULES.death.revive_coins,
        player_hp_before=player_hp_before,
        player_hp_after=player.hp,
        player_max_hp=player.max_hp,
        enemy_starts=enemy_starts,
        player_start=player_start,
        player_name=player.name,
        player_surprise=player_surprise,
    )


async def build_narrate_input(
    state: GameState,
    scenario_repo: ScenarioRepo,
    *,
    player_input: str,
    result: AutoCombatResult,
) -> CombatNarrateInput:
    player = state.characters[state.player_id]
    world = await build_world_layer(scenario_repo, state.profile, missing_ok=True)
    enemies_end = [
        _enemy_end_snapshot(state, h.id)
        for h in result.enemy_hits
        if h.id in state.characters
    ]
    history = [
        {"turn": e.turn, "target": e.target, "summary": e.summary}
        for e in state.turn_log[-5:]
    ]
    recent_dialogue = [
        {"turn": d.turn, "player": d.player, "narrator": d.narrator}
        for d in state.recent_dialogue[-2:]
    ]
    return CombatNarrateInput(
        world=world,
        location=_location_payload(state),
        player_view=build_player_view(state),
        player_intent=player_input,
        rounds_run=result.rounds_run,
        outcome=result.outcome,
        player_start=result.player_start,
        player_end=PlayerNarrateSnapshot(alive=player.alive),
        enemies_start=result.enemy_starts,
        enemies_end=enemies_end,
        events=result.events,
        history=history,
        recent_dialogue=recent_dialogue,
        surprise=result.player_surprise,
    )
