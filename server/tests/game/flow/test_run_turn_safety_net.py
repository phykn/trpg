"""run_turn safety net: if any unhandled exception fires mid-turn, the
streamed content (player input + whatever GM/engine lines made it into
`dirty`) must already be flushed to the save repo. Without this, the next
/turn loads the pre-error state and the user perceives the just-finished
turn as gone — the "기존 내용이 삭제 되는 것처럼 보인다" symptom.
"""

import random
import tempfile

import pytest

from src.db.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo
from src.game.domain.entities import Character, Location, Stats
from src.game.flow import turn as turn_mod
from src.game.flow.turn import run_turn


@pytest.fixture
def tmp_saves():
    with tempfile.TemporaryDirectory() as d:
        yield d


def _seed_minimal(state):
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
    return state


@pytest.mark.asyncio
async def test_player_input_persists_when_run_judge_raises_unexpectedly(
    fresh_state, tmp_saves, monkeypatch
):
    """An unhandled error (not JudgeMalformed/JudgeSemanticError, which the
    flow catches explicitly) raised by run_judge must still leave the player
    input in the save repo."""
    state = _seed_minimal(fresh_state)
    save_repo = LocalFsSaveRepo(saves_dir=str(tmp_saves))
    scenario_repo = LocalFsScenarioRepo(profile_dir="<unused>")
    await save_repo.save_meta(state)

    async def explode(*a, **kw):
        raise RuntimeError("simulated mid-turn crash")

    monkeypatch.setattr(turn_mod, "run_judge", explode)

    events: list[dict] = []
    with pytest.raises(RuntimeError, match="simulated mid-turn crash"):
        async for ev in run_turn(
            client=object(),
            state=state,
            scenario_repo=scenario_repo,
            save_repo=save_repo,
            player_input="이것은 테스트 입력",
            rng=random.Random(0),
        ):
            events.append(ev)

    reloaded = await save_repo.load_game(state.game_id)
    texts = [getattr(e, "text", None) for e in reloaded.log_entries]
    assert "이것은 테스트 입력" in texts, (
        f"player input not persisted to DB despite mid-turn error; got {texts}"
    )
