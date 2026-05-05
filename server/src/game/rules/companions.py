from pydantic import BaseModel, ConfigDict


class _F(BaseModel):
    model_config = ConfigDict(frozen=True)


class CompanionRules(_F):
    max_companions: int = 3
    recruit_base_dc: int = 12
    recruit_affinity_crit_success: int = 10
    recruit_affinity_success: int = 3
    recruit_affinity_crit_failure: int = -5
