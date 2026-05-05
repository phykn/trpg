from pydantic import BaseModel, ConfigDict

from .companions import CompanionRules
from ..domain.types import Tier


class _F(BaseModel):
    model_config = ConfigDict(frozen=True)


class DifficultyClass(_F):
    critical_hit_threshold: int = 20
    critical_miss_threshold: int = 1
    tier_dc_ranges: dict[Tier, tuple[int, int]] = {
        "very_easy": (2, 3),
        "easy": (4, 6),
        "normal": (7, 10),
        "hard": (11, 13),
        "very_hard": (14, 16),
        "legend": (17, 18),
        "myth": (19, 19),
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
    recent_dialogue_turns: int = 10


class LogConfig(_F):
    display_turns: int = 20


class TimeConfig(_F):
    phase_turns: int = 10


class RecoveryConfig(_F):
    encounter_chance: dict[str, float] = {
        "safe": 0.0,
        "risky": 0.25,
        "dangerous": 0.6,
    }
    cost_gold: int = 10


class GrowthConfig(_F):
    base_xp: int = 100
    max_level: int = 20
    roll_xp: dict[str, int] = {
        "critical_success": 25,
        "success": 8,
        "partial_success": 3,
        "failure": 0,
        "critical_failure": 0,
    }


class SkillConfig(_F):
    grade_multipliers: dict[str, float] = {
        "critical_success": 2.0,
        "success": 1.0,
        "partial_success": 0.5,
        "failure": 0.0,
        "critical_failure": 0.0,
    }
    recommend_recent_turns: int = 10
    recommend_recent_inputs: int = 5


class CarryConfig(_F):
    weight_per_strength: float = 10.0


class TradeConfig(_F):
    sell_ratio: float = 0.5
    affinity_price_per_point: float = 0.01
    affinity_price_cap: float = 0.5


class FleeConfig(_F):
    dice: str = "1d20"
    base_dc: int = 12
    dex_modifier: bool = True


class UnarmedConfig(_F):
    damage: str = "1d4"
    range_m: float = 1.5


class CombatConfig(_F):
    flee: FleeConfig = FleeConfig()
    unarmed: UnarmedConfig = UnarmedConfig()


class DeathConfig(_F):
    instant_death: bool = False
    revive_coins: int = 3
    save_dc: int = 10
    successes_to_stabilize: int = 3
    failures_to_die: int = 3
    damage_failure_inc: int = 1
    crit_damage_failure_inc: int = 2
    auto_revive_hp: int = 1


class LLMConfig(_F):
    # Override the OpenAI client's ~10min default so a stalled LLM can't hang the whole turn.
    chat_timeout_s: float = 60.0
    stream_timeout_s: float = 180.0


class Rules(_F):
    difficulty_class: DifficultyClass = DifficultyClass()
    social: Social = Social()
    memory: MemoryConfig = MemoryConfig()
    log: LogConfig = LogConfig()
    time: TimeConfig = TimeConfig()
    carry: CarryConfig = CarryConfig()
    trade: TradeConfig = TradeConfig()
    combat: CombatConfig = CombatConfig()
    death: DeathConfig = DeathConfig()
    recovery: RecoveryConfig = RecoveryConfig()
    growth: GrowthConfig = GrowthConfig()
    skill: SkillConfig = SkillConfig()
    llm: LLMConfig = LLMConfig()
    companions: CompanionRules = CompanionRules()


RULES = Rules()
