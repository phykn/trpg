"""Long rest at the current location.

자연 회복 없음 — HP/MP 는 잠을 자야 회복된다 (docs/03-features.md §2.4).
attempt_rest 가 위험도 굴림으로 인카운터 vs 풀회복을 가른다. 풀회복이면 HP/MP 를 max 로
올리고 world_time 을 sleep_hours 만큼 진행. 인카운터면 enemy_ids 를 반환하고
호출자가 combat 부팅까지 책임 (turn.py).

시드 sleep_encounters 풀이 비어 있고 LLM summon 콜백이 주어지면 즉석 적 1마리를 생성
한다 (P3 §2.4 폴백).
"""

import random
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Literal

from ..rules import RULES
from ..domain.state import GameState

RestOutcome = Literal["full_recovery", "encounter"]
SummonCallable = Callable[[GameState, str], Awaitable[str | None]]
"""(state, location_id) → 등록된 character_id 또는 None. None 이면 폴백 풀회복."""


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
) -> tuple[RestOutcome, list[str]]:
    """위험도 굴림으로 인카운터 vs 풀회복.

    인카운터 발동 + sleep_encounters 풀이 비어 있으면 `summon` 콜백으로 LLM 즉석 적
    생성을 시도. summon=None 또는 실패 시 풀회복 폴백 — 잠을 깨지 않는 다행한 밤.
    encounter 반환 시 enemy_ids 는 모두 state.characters 에 등록된 상태.
    """
    rng_obj = rng or random
    actor = state.characters[actor_id]
    if actor.location_id is None:
        # 무국적 캐릭터 — 그냥 풀회복 + 시간 점프.
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
            # 잠들기 직전 습격 — 시간은 흐르지 않는다 (combat 이 자체 시간 가산).
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
