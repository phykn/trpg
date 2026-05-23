from pydantic import BaseModel, ConfigDict

from ..domain.types import EncounterRisk, Grade, Tier


class _F(BaseModel):
    model_config = ConfigDict(frozen=True)


class CompanionRules(_F):
    max_companions: int = 3
    recruit_base_dc: int = 12
    recruit_affinity_crit_success: int = 10
    recruit_affinity_success: int = 3
    recruit_affinity_crit_failure: int = -5


class DifficultyClass(_F):
    critical_hit_threshold: int = 20
    critical_miss_threshold: int = 1
    tier_dc_ranges: dict[Tier, tuple[int, int]] = {
        "easy": (2, 7),
        "normal": (8, 13),
        "hard": (14, 19),
    }


class Social(_F):
    friendly_threshold: int = 50
    roll_bonus: int = 2
    affinity_success: int = 5
    affinity_failure: int = -3
    affinity_critical: int = 10
    trade_threshold: int = 0
    combat_affinity_drop: int = 20
    # Override `relations[player]` so hostile seeds carrying gear don't surface as merchants on first sight.
    hostile_aggressive_threshold: int = 70


class MemoryConfig(_F):
    cap: int = 20
    turn_log_size: int = 50
    recent_exchange_turns: int = 10


class LogConfig(_F):
    display_turns: int = 20


class RecoveryConfig(_F):
    encounter_chance: dict[EncounterRisk, float] = {
        "safe": 0.0,
        "risky": 0.25,
        "dangerous": 0.6,
    }
    cost_gold: int = 10


class GrowthConfig(_F):
    base_xp: int = 1
    max_level: int = 10
    roll_xp: dict[Grade, int] = {
        "critical_success": 2,
        "success": 1,
        "failure": 0,
        "critical_failure": 0,
    }


class SkillConfig(_F):
    grade_multipliers: dict[Grade, float] = {
        "critical_success": 2.0,
        "success": 1.0,
        "failure": 0.0,
        "critical_failure": 0.0,
    }


class CarryConfig(_F):
    weight_per_strength: float = 10.0


class TradeConfig(_F):
    sell_ratio: float = 0.5
    affinity_price_per_point: float = 0.01
    affinity_price_cap: float = 0.5


class UnarmedConfig(_F):
    damage: str = "1d4"
    range_m: float = 1.5


class CombatConfig(_F):
    base_dc: int = 11
    min_dc: int = 6
    max_dc: int = 18
    starting_hearts: int = 3
    unarmed: UnarmedConfig = UnarmedConfig()


class Rules(_F):
    difficulty_class: DifficultyClass = DifficultyClass()
    social: Social = Social()
    memory: MemoryConfig = MemoryConfig()
    log: LogConfig = LogConfig()
    carry: CarryConfig = CarryConfig()
    trade: TradeConfig = TradeConfig()
    combat: CombatConfig = CombatConfig()
    recovery: RecoveryConfig = RecoveryConfig()
    growth: GrowthConfig = GrowthConfig()
    skill: SkillConfig = SkillConfig()
    companions: CompanionRules = CompanionRules()


RULES = Rules()
