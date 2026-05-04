from src.domain.entities import Character, Stats
from src.domain.memory import PendingCheck
from src.flow.companion import handle_recruit_roll_result
from src.flow.dirty import Dirty


def _setup_state(fresh_state, *, edric_affinity=30):
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        location_id="plaza_01",
        stats=Stats(STR=10, DEX=10, CON=10, INT=10, WIS=10, CHA=12),
        hp=20,
        max_hp=20,
        companions=[],
    )
    fresh_state.characters["npc.edric"] = Character(
        id="npc.edric",
        name="에드릭",
        race_id="human",
        location_id="plaza_01",
        stats=Stats(STR=12, DEX=10, CON=10, INT=10, WIS=10, CHA=10),
        hp=15,
        max_hp=15,
        relations={"player_01": edric_affinity},
    )
    return fresh_state


def _recruit_pending(target="npc.edric"):
    return PendingCheck(
        player_input="에드릭, 함께 가자",
        kind="recruit",
        tier="보통",
        stat="CHA",
        target=target,
        targets=[target],
        dc=10,
        mod=0,
        required_roll=10,
        reason="동료 영입",
        created_at="2026-05-04T00:00:00",
    )


async def test_critical_success_adds_companion_with_big_bonus(fresh_state, collect):
    state = _setup_state(fresh_state, edric_affinity=30)
    pending = _recruit_pending()
    dirty = Dirty()

    events = await collect(
        handle_recruit_roll_result(state, pending, "critical_success", dirty)
    )

    assert "npc.edric" in state.characters["player_01"].companions
    assert state.characters["npc.edric"].relations["player_01"] == 40  # 30 + 10
    assert state.previous_phase_signal == "companion_joined:에드릭"
    assert any(
        ev.get("type") == "log_entry"
        and (ev.get("data") or {}).get("text") == "에드릭이 동료가 되었습니다."
        for ev in events
    )


async def test_success_adds_companion_with_small_bonus(fresh_state, collect):
    state = _setup_state(fresh_state, edric_affinity=30)
    pending = _recruit_pending()
    dirty = Dirty()

    await collect(handle_recruit_roll_result(state, pending, "success", dirty))

    assert "npc.edric" in state.characters["player_01"].companions
    assert state.characters["npc.edric"].relations["player_01"] == 33  # 30 + 3
    assert state.previous_phase_signal == "companion_joined:에드릭"


async def test_partial_success_adds_companion(fresh_state, collect):
    state = _setup_state(fresh_state, edric_affinity=30)
    pending = _recruit_pending()
    dirty = Dirty()

    await collect(handle_recruit_roll_result(state, pending, "partial_success", dirty))

    assert "npc.edric" in state.characters["player_01"].companions
    assert state.characters["npc.edric"].relations["player_01"] == 33
    assert state.previous_phase_signal == "companion_joined:에드릭"


async def test_failure_keeps_affinity_unchanged(fresh_state, collect):
    state = _setup_state(fresh_state, edric_affinity=30)
    pending = _recruit_pending()
    dirty = Dirty()

    events = await collect(handle_recruit_roll_result(state, pending, "failure", dirty))

    assert "npc.edric" not in state.characters["player_01"].companions
    assert state.characters["npc.edric"].relations["player_01"] == 30
    assert state.previous_phase_signal == "companion_refused:에드릭"
    assert any(
        ev.get("type") == "log_entry"
        and (ev.get("data") or {}).get("text") == "에드릭이 제안을 거절합니다."
        for ev in events
    )


async def test_critical_failure_drops_affinity(fresh_state, collect):
    state = _setup_state(fresh_state, edric_affinity=30)
    pending = _recruit_pending()
    dirty = Dirty()

    events = await collect(
        handle_recruit_roll_result(state, pending, "critical_failure", dirty)
    )

    assert "npc.edric" not in state.characters["player_01"].companions
    assert state.characters["npc.edric"].relations["player_01"] == 25  # 30 - 5
    assert state.previous_phase_signal == "companion_refused:에드릭"
    assert any(
        ev.get("type") == "log_entry"
        and (ev.get("data") or {}).get("text") == "에드릭이 노골적으로 거절합니다."
        for ev in events
    )
