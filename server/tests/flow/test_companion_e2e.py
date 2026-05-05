"""End-to-end recruit→roll→dismiss cycle. Drives run_turn for the recruit
intent, /roll for the resolution, then run_turn for dismiss. Verifies the
companions list mutates correctly across the three steps."""

import random

from src.domain.entities import Character, Stats
from src.flow import roll as roll_mod
from src.flow.roll import run_roll
from src.flow.turn import run_turn
from src.llm.calls.classify.schema import Verb
from src.persistence.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo


def _seed_state(fresh_state, edric_affinity=80):
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        location_id="plaza_01",
        stats=Stats(STR=10, DEX=10, CON=10, INT=10, WIS=10, CHA=14),
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


async def test_recruit_then_dismiss_cycle(
    fresh_state, tmp_data, judge_returns, collect, monkeypatch
):
    state = _seed_state(fresh_state, edric_affinity=80)

    save_repo = LocalFsSaveRepo(saves_dir=str(tmp_data))
    scenario_repo = LocalFsScenarioRepo(profile_dir="<unused>")

    # 1) Player input "에드릭, 함께 가자" → judge returns RecruitAction → run_recruit emits pending
    judge_returns(Verb(name="speak", modifiers={"intent": "recruit", "target": "npc.edric"}))
    await collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=scenario_repo,
            save_repo=save_repo,
            player_input="에드릭, 함께 가자",
        )
    )
    assert state.pending_check is not None
    assert state.pending_check.kind == "recruit"

    # 2) /roll: force a success grade by patching compute_grade
    monkeypatch.setattr(roll_mod, "compute_grade", lambda nat, total, req: "success")
    await collect(
        run_roll(
            client=None,
            state=state,
            scenario_repo=scenario_repo,
            save_repo=save_repo,
            rng=random.Random(42),
        )
    )
    assert state.pending_check is None
    assert "npc.edric" in state.characters["player_01"].companions
    assert state.previous_phase_signal == "companion_joined:에드릭"

    # 3) Player input "에드릭, 헤어지자" → judge returns DismissAction → companion removed
    judge_returns(Verb(name="speak", modifiers={"intent": "part", "target": "npc.edric"}))
    await collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=scenario_repo,
            save_repo=save_repo,
            player_input="에드릭, 이제 헤어지자",
        )
    )
    assert "npc.edric" not in state.characters["player_01"].companions
    assert state.previous_phase_signal == "companion_dismissed:에드릭"


async def test_recruit_critical_failure_drops_affinity_no_companion(
    fresh_state, tmp_data, judge_returns, collect, monkeypatch
):
    """A critical_failure recruit roll: no companion added, affinity drops by 5."""
    state = _seed_state(fresh_state, edric_affinity=20)
    save_repo = LocalFsSaveRepo(saves_dir=str(tmp_data))
    scenario_repo = LocalFsScenarioRepo(profile_dir="<unused>")

    judge_returns(Verb(name="speak", modifiers={"intent": "recruit", "target": "npc.edric"}))
    await collect(
        run_turn(
            client=None,
            state=state,
            scenario_repo=scenario_repo,
            save_repo=save_repo,
            player_input="에드릭, 함께 가자",
        )
    )

    monkeypatch.setattr(roll_mod, "compute_grade", lambda nat, total, req: "critical_failure")
    await collect(
        run_roll(
            client=None,
            state=state,
            scenario_repo=scenario_repo,
            save_repo=save_repo,
            rng=random.Random(99),
        )
    )

    assert "npc.edric" not in state.characters["player_01"].companions
    assert state.characters["npc.edric"].relations["player_01"] == 15  # 20 - 5
    assert state.previous_phase_signal == "companion_refused:에드릭"
