from src.domain.entities import Character, Stats
from src.flow.companion import run_dismiss
from src.flow.dirty import Dirty
from src.flow.turn import run_turn
from src.llm_calls.classify.schema import DismissAction
from src.persistence.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo


_SCENARIO_REPO = LocalFsScenarioRepo(profile_dir="<unused>")


def _setup_state_with_companion(fresh_state):
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        location_id="plaza_01",
        stats=Stats(STR=10, DEX=10, CON=10, INT=10, WIS=10, CHA=12),
        hp=20,
        max_hp=20,
        companions=["npc.edric"],
    )
    fresh_state.characters["npc.edric"] = Character(
        id="npc.edric",
        name="에드릭",
        race_id="human",
        location_id="plaza_01",
        stats=Stats(STR=12, DEX=10, CON=10, INT=10, WIS=10, CHA=10),
        hp=15,
        max_hp=15,
    )
    return fresh_state


async def test_dismiss_removes_companion(fresh_state, tmp_data, collect):
    state = _setup_state_with_companion(fresh_state)
    save_repo = LocalFsSaveRepo(saves_dir=str(tmp_data))
    dirty = Dirty()

    events = await collect(
        run_dismiss(state, _SCENARIO_REPO, save_repo, None, "npc.edric", dirty, None)
    )

    assert "npc.edric" not in state.characters["player_01"].companions
    assert state.previous_phase_signal == "companion_dismissed:에드릭"
    assert any(
        ev.get("type") == "log_entry"
        and (ev.get("data") or {}).get("text") == "에드릭이 일행에서 빠집니다."
        for ev in events
    )


async def test_dismiss_target_not_in_companions_no_op(fresh_state, tmp_data, collect):
    """Defensive: judge should reject this, but if it slips through, no-op safely."""
    state = fresh_state
    state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        location_id="plaza_01",
        stats=Stats(STR=10, DEX=10, CON=10, INT=10, WIS=10, CHA=10),
        hp=20,
        max_hp=20,
        companions=[],
    )
    state.characters["npc.edric"] = Character(
        id="npc.edric",
        name="에드릭",
        race_id="human",
        location_id="plaza_01",
        stats=Stats(STR=10, DEX=10, CON=10, INT=10, WIS=10, CHA=10),
        hp=15,
        max_hp=15,
    )
    save_repo = LocalFsSaveRepo(saves_dir=str(tmp_data))
    dirty = Dirty()

    await collect(
        run_dismiss(state, _SCENARIO_REPO, save_repo, None, "npc.edric", dirty, None)
    )

    assert "npc.edric" not in state.characters["player_01"].companions
    assert state.previous_phase_signal != "companion_dismissed:에드릭"


async def test_dismiss_records_turn_log(fresh_state, tmp_data, collect):
    state = _setup_state_with_companion(fresh_state)
    save_repo = LocalFsSaveRepo(saves_dir=str(tmp_data))
    dirty = Dirty()

    await collect(
        run_dismiss(state, _SCENARIO_REPO, save_repo, None, "npc.edric", dirty, None)
    )

    assert any(
        getattr(entry, "summary", None) == "에드릭 동행 이탈"
        for entry in state.turn_log
    )


async def test_dismiss_via_run_turn(
    fresh_state, tmp_data, judge_returns, collect
):
    """run_turn → judge returns DismissAction → run_dismiss is invoked."""
    state = _setup_state_with_companion(fresh_state)
    judge_returns(DismissAction(action="dismiss", target="npc.edric"))

    await collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="에드릭, 이제 헤어지자",
        )
    )

    assert "npc.edric" not in state.characters["player_01"].companions
    assert state.previous_phase_signal == "companion_dismissed:에드릭"
