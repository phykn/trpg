"""Affinity round-trip: a narrate-emitted hostile-success affinity drop must
both persist to the entity DB (target.relations[actor] reflects the delta on
reload) and persist the system card to the log DB (next turn's display still
sees it within the trim window).

Reported symptom: the system card showed -5 mid-turn, but next turn the card
was gone from the log AND the UI affinity pill still read 0.
"""

import random
import tempfile

import pytest

from src.db.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo
from src.game.domain.entities import Character, Location, Stats
from src.game.flow import narrate as narrate_mod
from src.game.flow import turn as turn_mod
from src.game.flow.turn import run_turn
from src.llm.calls.classify.schema import JudgeOutput, Verb
from src.llm.calls.narrate import NarrativeDelta, NarrativeFinal
from src.llm.calls.narrate.schema import NarrateOutput


@pytest.fixture
def tmp_saves():
    with tempfile.TemporaryDirectory() as d:
        yield d


def _seed(state):
    state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        location_id="plaza_01",
        stats=Stats(),
        hp=10,
        max_hp=10,
    )
    state.characters["edrik_chief"] = Character(
        id="edrik_chief",
        name="에드릭",
        race_id="human",
        location_id="plaza_01",
        stats=Stats(),
        hp=10,
        max_hp=10,
        relations={},
    )
    return state


@pytest.mark.asyncio
async def test_affinity_drop_persists_through_full_turn(
    fresh_state, tmp_saves, monkeypatch
):
    """Hostile-success speak verb → narrate emits affinity state_change →
    apply_changes drops target.relations[actor] by 5 and pushes a system
    card. After finalize the entity reload must show -5 and the log reload
    must contain the card."""
    state = _seed(fresh_state)
    save_repo = LocalFsSaveRepo(saves_dir=str(tmp_saves))
    scenario_repo = LocalFsScenarioRepo(profile_dir="<unused>")
    await save_repo.save_meta(state)

    async def fake_judge(*a, **kw):
        return JudgeOutput(
            actions=[
                Verb(
                    name="speak",
                    modifiers={"intent": "hostile", "target": "edrik_chief"},
                )
            ]
        )

    monkeypatch.setattr(turn_mod, "run_judge", fake_judge)

    async def fake_run_narrate(*a, **kw):
        yield NarrativeDelta(text="당신은 에드릭에게 모욕을 던집니다.")
        yield NarrativeFinal(
            body="당신은 에드릭에게 모욕을 던집니다.",
            output=NarrateOutput(
                turn_summary="에드릭 모욕",
                state_changes=[
                    {
                        "type": "affinity",
                        "actor": "player_01",
                        "target": "edrik_chief",
                        "grade": "success",
                        "intent": "hostile",
                    }
                ],
                memorable=False,
                memory_targets=[],
                memory={},
                memory_links={},
                importance=None,
                suggestions=[],
            ),
        )

    monkeypatch.setattr(narrate_mod, "run_narrate", fake_run_narrate)

    events: list[dict] = []
    async for ev in run_turn(
        client=object(),
        state=state,
        scenario_repo=scenario_repo,
        save_repo=save_repo,
        player_input="에드릭에게 욕을 한다",
        rng=random.Random(0),
    ):
        events.append(ev)

    reloaded = await save_repo.load_game(state.game_id)
    npc = reloaded.characters["edrik_chief"]
    assert npc.relations.get("player_01") == -5, (
        f"affinity not persisted; got relations={npc.relations}"
    )

    log_texts = [getattr(e, "text", "") for e in reloaded.log_entries]
    assert any("호감도" in t and "-5" in t for t in log_texts), (
        f"affinity card not persisted to log; got log_texts={log_texts}"
    )
