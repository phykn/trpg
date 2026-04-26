from pydantic import BaseModel, ConfigDict


class _F(BaseModel):
    model_config = ConfigDict(frozen=True)


class SigmoidDC(_F):
    k: float = 0.5


class DifficultyClass(_F):
    sigmoid: SigmoidDC = SigmoidDC()
    critical_hit_threshold: int = 20
    critical_miss_threshold: int = 1
    tier_dc_ranges: dict[str, tuple[int, int]] = {
        "매우 쉬움": (2, 3),
        "쉬움": (4, 6),
        "보통": (7, 10),
        "어려움": (11, 13),
        "매우 어려움": (14, 16),
        "전설": (17, 18),
        "신화": (19, 19),
    }


class Social(_F):
    friendly_threshold: int = 50
    roll_bonus: int = 2
    affinity_success: int = 5
    affinity_failure: int = -3
    affinity_critical: int = 10
    trade_threshold: int = 0


class MemoryConfig(_F):
    cap: int = 20
    turn_log_size: int = 50
    recent_dialogue_turns: int = 10


class LogConfig(_F):
    display_turns: int = 20


class TimeConfig(_F):
    turn_min: int = 1


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
    revive_coins: int = 1
    revive_ratio: float = 0.5
    save_dc: int = 10
    successes_to_stabilize: int = 3
    failures_to_die: int = 3
    damage_failure_inc: int = 1
    crit_damage_failure_inc: int = 2
    auto_revive_hp: int = 1


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


RULES = Rules()
