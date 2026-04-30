"""One-roll combat resolution.

Combat in this game is a **single d20 check** rather than round-by-round
mechanics. Player declares intent ("고블린을 친다") → judge classifies as
CombatAction → flow arms `pending_check kind="combat_roll"` → client
shows the dice button → player clicks → /roll resolves the whole fight in
one beat:

- The d20 + STR vs DC produces a grade (critical_success → critical_failure).
- Grade maps to a mechanical outcome (kills, HP damage, XP, downed state).
- `combat_narrate` streams a 5–10 sentence cinematic scene of the entire
  fight, tone matched to the grade.

Death-save handling shares the dice-prompt mechanism (`kind="death_save"`)
since both are "press the button to roll".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from ..agents.combat_narrate import (
    CombatNarrateInput,
    CombatRoundEvent,
    CombatStateSnapshot,
)
from ..context.layers import build_world_layer
from ..domain.entities import Character
from ..domain.memory import PendingCheck
from ..domain.state import GameState
from ..domain.types import Grade
from ..engines import combat as combat_engine
from ..engines.growth import award_kill_xp
from ..rules.config import RULES
from ..rules.dc import compute_required_roll, tier_mid_dc
from .dirty import Dirty, register_kill


# --- Outcome report --------------------------------------------------------


@dataclass
class EnemyHit:
    """Per-enemy slice of a one-roll combat result. Used by the outcome
    formatter to render the post-cinematic numeric breakdown."""
    id: str
    name: str
    damage: int
    hp_after: int
    max_hp: int
    killed: bool
    xp: int


@dataclass
class CombatOutcomeReport:
    enemy_hits: list[EnemyHit] = field(default_factory=list)
    player_damage: int = 0
    player_hp_after: int = 0
    player_max_hp: int = 0


# --- Snapshots / context for combat_narrate --------------------------------


def _location_payload(state: GameState) -> dict:
    actor = state.characters.get(state.player_id)
    if actor is None or actor.location_id is None:
        return {}
    loc = state.locations.get(actor.location_id)
    if loc is None:
        return {}
    return {
        "id": loc.id,
        "name": loc.name,
        "description": loc.description,
        "tags": list(loc.tags),
        "weather": loc.weather,
    }


# --- Pending-check arming --------------------------------------------------


def arm_death_save_pending(state: GameState) -> None:
    """Set a pending_check that the client renders as a dice button. /roll
    will branch on `kind="death_save"` and feed the d20 to tick_death_save."""
    state.pending_check = PendingCheck(
        player_input="죽음 굴림",
        kind="death_save",
        tier="쉬움",
        stat="CON",
        target=state.player_id,
        targets=[state.player_id],
        dc=RULES.death.save_dc,
        mod=0,
        required_roll=RULES.death.save_dc,
        reason="죽음 굴림",
        created_at=datetime.now(UTC).isoformat(),
    )


def _pick_combat_tier(num_enemies: int) -> str:
    """Multi-target combat is harder. Single foe = 보통, party = 어려움+."""
    if num_enemies <= 1:
        return "보통"
    if num_enemies <= 3:
        return "어려움"
    return "매우 어려움"


def arm_combat_roll_pending(
    state: GameState,
    *,
    target_ids: list[str],
    player_input: str,
    skill_id: str | None = None,
) -> None:
    """Arm the dice-button pending_check for one-roll combat resolution.

    Difficulty scales with enemy count. STR is the default attack stat;
    /roll's combat_roll branch will read this back to compute the grade
    and apply the outcome.
    """
    tier = _pick_combat_tier(len(target_ids))
    dc = tier_mid_dc(tier)
    primary = target_ids[0] if target_ids else state.player_id
    actor = state.characters[state.player_id]
    required_roll = compute_required_roll(dc, getattr(actor.stats, "STR"))
    state.pending_check = PendingCheck(
        player_input=player_input,
        kind="combat_roll",
        tier=tier,
        stat="STR",
        target=primary,
        targets=list(target_ids),
        dc=dc,
        mod=0,
        required_roll=required_roll,
        reason=skill_id or "전투 굴림",
        created_at=datetime.now(UTC).isoformat(),
    )


# --- One-roll combat outcome -----------------------------------------------


# grade → (player damage as % of max_hp, kill all enemies)
_OUTCOME_TABLE: dict[Grade, tuple[float, bool]] = {
    "critical_success": (0.0, True),
    "success": (0.10, True),
    "partial_success": (0.30, True),
    "failure": (0.55, False),
    "critical_failure": (1.00, False),
}


def apply_combat_outcome(
    state: GameState,
    target_ids: list[str],
    grade: Grade,
    dirty: Dirty,
) -> CombatOutcomeReport:
    """Apply mechanical effects of a one-roll combat and return a per-enemy
    breakdown plus the player's hit. The returned report drives the numeric
    post-cinematic act-line so the player can see the actual damage / HP /
    kill XP behind the prose.

    - critical_success / success / partial_success → kill all enemies, take
      a grade-scaled chunk of HP. XP is awarded per kill.
    - failure → enemies survive at half HP, player takes heavy damage.
    - critical_failure → enemies survive at full HP, player drops to 0
      (death-saves trigger).
    """
    player = state.characters[state.player_id]
    player_dmg_pct, kill_enemies = _OUTCOME_TABLE[grade]

    report = CombatOutcomeReport()
    for tid in target_ids:
        if tid not in state.characters:
            continue
        enemy: Character = state.characters[tid]
        if not enemy.alive:
            continue
        if kill_enemies:
            damage = enemy.hp
            combat_engine.apply_attack_to_defender(
                state, tid, damage, dirty=dirty.entities,
            )
            killed = not enemy.alive
            if killed:
                register_kill(state, tid, dirty)
            xp = (
                award_kill_xp(state, state.player_id, tid, dirty=dirty.entities)
                if killed else 0
            )
            report.enemy_hits.append(EnemyHit(
                id=tid, name=enemy.name, damage=damage,
                hp_after=enemy.hp, max_hp=enemy.max_hp,
                killed=killed, xp=xp,
            ))
        else:
            damage = max(1, enemy.hp // 2)
            combat_engine.apply_attack_to_defender(
                state, tid, damage, dirty=dirty.entities,
            )
            report.enemy_hits.append(EnemyHit(
                id=tid, name=enemy.name, damage=damage,
                hp_after=enemy.hp, max_hp=enemy.max_hp,
                killed=False, xp=0,
            ))

    player_damage = int(round(player.max_hp * player_dmg_pct))
    if player_damage > 0:
        combat_engine.apply_attack_to_defender(
            state, player.id, player_damage, dirty=dirty.entities,
        )
        if not player.alive:
            register_kill(state, player.id, dirty)
    report.player_damage = player_damage
    report.player_hp_after = player.hp
    report.player_max_hp = player.max_hp
    return report


def format_combat_outcome_text(
    report: CombatOutcomeReport, roll_xp: int
) -> str | None:
    """Numeric breakdown rendered as one act-line after the cinematic body —
    per-enemy damage / HP / kill XP, the player's hit, and any per-roll XP
    earned. Returns None when there is nothing to report (e.g. no enemies
    registered, no damage, no XP)."""
    lines: list[str] = []
    for h in report.enemy_hits:
        if h.killed:
            tail = f" — 쓰러짐 (+{h.xp} XP)" if h.xp > 0 else " — 쓰러짐"
            lines.append(f"{h.name} {h.damage} 피해{tail}")
        else:
            lines.append(
                f"{h.name} {h.damage} 피해 (HP {h.hp_after}/{h.max_hp})"
            )
    if report.player_damage > 0:
        lines.append(
            f"피격 {report.player_damage} 피해 "
            f"(HP {report.player_hp_after}/{report.player_max_hp})"
        )
    if roll_xp > 0:
        lines.append(f"굴림 경험치 +{roll_xp}")
    if not lines:
        return None
    return "전투 결과\n" + "\n".join(lines)


def build_oneshot_narrate_input(
    state: GameState,
    profile_dir: str,
    *,
    player_input: str,
    target_ids: list[str],
    grade: str,
    player_damage: int,
    killed_enemy_ids: list[str],
) -> CombatNarrateInput:
    """Build a CombatNarrateInput that frames a one-roll combat as a single
    `is_first_round=True, is_final_round=True` round so the existing
    combat_narrate prompt (round-shaped) writes the whole fight in one beat."""
    player = state.characters[state.player_id]
    world = build_world_layer(profile_dir, state.profile, missing_ok=True)
    location = _location_payload(state)

    enemy_names = []
    enemy_snaps: list[CombatStateSnapshot] = []
    for tid in target_ids:
        ch = state.characters.get(tid)
        if ch is None:
            continue
        enemy_names.append(ch.name)
        enemy_snaps.append(CombatStateSnapshot(name=ch.name, hp=ch.hp, max_hp=ch.max_hp, alive=ch.alive))

    events: list[CombatRoundEvent] = []
    won = grade in ("critical_success", "success", "partial_success")
    for tid in target_ids:
        ch = state.characters.get(tid)
        if ch is None:
            continue
        events.append(CombatRoundEvent(
            actor=player.name,
            target=ch.name,
            action="attack" if won else "miss",
            grade=grade,
            damage=ch.max_hp if (tid in killed_enemy_ids) else 0,
            killed=(tid in killed_enemy_ids),
        ))
    if player_damage > 0 and enemy_names:
        events.append(CombatRoundEvent(
            actor=enemy_names[0],
            target=player.name,
            action="attack",
            grade="critical_success" if grade == "critical_failure" else "success",
            damage=player_damage,
            killed=not player.alive,
        ))

    return CombatNarrateInput(
        world=world,
        location=location,
        player_intent=player_input,
        round_no=1,
        is_first_round=True,
        is_final_round=True,
        player=CombatStateSnapshot(name=player.name, hp=player.hp, max_hp=player.max_hp, alive=player.alive),
        enemies=enemy_snaps,
        events=events,
        history_summary="",
    )


