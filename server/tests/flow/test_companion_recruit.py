from src.domain.entities import Character, Stats
from src.flow.companion import run_recruit
from src.flow.dirty import Dirty
from src.flow.turn import run_turn
from src.llm_calls.classify.schema import RecruitAction
from src.persistence.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo


def _setup_state(fresh_state, *, edric_affinity=50):
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


async def test_recruit_emits_pending_check(fresh_state, tmp_data, collect):
    state = _setup_state(fresh_state, edric_affinity=50)
    save_repo = LocalFsSaveRepo(saves_dir=str(tmp_data))
    dirty = Dirty()

    events = await collect(
        run_recruit(state, save_repo, "에드릭, 함께 가자", "npc.edric", dirty, None)
    )

    assert state.pending_check is not None
    assert state.pending_check.kind == "recruit"
    assert state.pending_check.stat == "CHA"
    assert state.pending_check.target == "npc.edric"
    # base 12 - clamp(50/10=5, -5, +5) = 12 - 5 = 7
    assert state.pending_check.dc == 7
    assert any(ev.get("type") == "pending_check" for ev in events)


async def test_recruit_dc_clamps_at_high_affinity(fresh_state, tmp_data, collect):
    state = _setup_state(fresh_state, edric_affinity=200)
    save_repo = LocalFsSaveRepo(saves_dir=str(tmp_data))
    dirty = Dirty()

    await collect(
        run_recruit(state, save_repo, "에드릭, 함께 가자", "npc.edric", dirty, None)
    )

    # base 12 - clamp(200/10=20, -5, +5) = 12 - 5 = 7
    assert state.pending_check.dc == 7


async def test_recruit_dc_neutral_affinity(fresh_state, tmp_data, collect):
    state = _setup_state(fresh_state, edric_affinity=0)
    save_repo = LocalFsSaveRepo(saves_dir=str(tmp_data))
    dirty = Dirty()

    await collect(
        run_recruit(state, save_repo, "에드릭, 함께 가자", "npc.edric", dirty, None)
    )

    # base 12 - clamp(0/10=0, -5, +5) = 12
    assert state.pending_check.dc == 12


async def test_recruit_dc_low_affinity(fresh_state, tmp_data, collect):
    """Negative affinity (just below the auto-reject threshold) raises DC."""
    state = _setup_state(fresh_state, edric_affinity=-30)
    save_repo = LocalFsSaveRepo(saves_dir=str(tmp_data))
    dirty = Dirty()

    await collect(
        run_recruit(state, save_repo, "에드릭, 동료가 되어줘", "npc.edric", dirty, None)
    )

    # base 12 - clamp(-30/10=-3, -5, +5) = 12 - (-3) = 15
    assert state.pending_check.dc == 15


async def test_recruit_dc_clamps_at_low_affinity(fresh_state, tmp_data, collect):
    """Negative affinity clamp boundary: -50 // 10 = -5, hits the floor."""
    state = _setup_state(fresh_state, edric_affinity=-50)
    # Lower the friendly threshold check would normally trip here, but recruit
    # is gated by classify semantics, not by the DC. The DC computation itself
    # should clamp.
    save_repo = LocalFsSaveRepo(saves_dir=str(tmp_data))
    dirty = Dirty()

    await collect(
        run_recruit(state, save_repo, "에드릭, 함께 가자", "npc.edric", dirty, None)
    )

    # base 12 - clamp(-50 // 10 = -5, -5, +5) = 12 - (-5) = 17
    assert state.pending_check.dc == 17


async def test_recruit_via_run_turn(
    fresh_state, tmp_data, judge_returns, collect
):
    """run_turn → judge returns RecruitAction → run_recruit emits pending_check."""
    state = _setup_state(fresh_state, edric_affinity=50)
    judge_returns(RecruitAction(action="recruit", target="npc.edric"))

    await collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_data)),
            player_input="에드릭, 함께 가자",
        )
    )

    assert state.pending_check is not None
    assert state.pending_check.kind == "recruit"
    assert state.pending_check.target == "npc.edric"
