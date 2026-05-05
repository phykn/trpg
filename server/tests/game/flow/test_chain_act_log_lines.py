"""Chain dispatch hands narrate the engine notices its non-final parts
emitted, so the body can reflect skipped/blocked operations instead of
pretending they succeeded.

Without this, narrate sees only `player_input` ("약초 먹고 검 든다") and the
final `pass`; if the heal silently skipped at the engine layer ("이미 체력
가득"), the body still describes drinking the herb.
"""

import tempfile

import pytest

from src.llm.calls.classify.schema import JudgeOutput, Verb
from src.game.domain.entities import (
    Character,
    ConsumableEffect,
    Item,
    Location,
    Stats,
)
from src.game.flow import narrate as narrate_mod
from src.game.flow import turn as turn_mod
from src.db.local_fs import LocalFsSaveRepo, LocalFsScenarioRepo
from src.game.flow.turn import run_turn


@pytest.fixture
def tmp_saves():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def state_full_hp_with_heal(fresh_state):
    fresh_state.locations["plaza_01"] = Location(id="plaza_01", name="광장")
    # heal item — engine raises InventoryInvalid("hp already full") when used
    # at full HP; emit_use catches it and pushes an act log line.
    fresh_state.items["herb_01"] = Item(
        id="herb_01",
        name="약초 꾸러미",
        consumable=True,
        effects=ConsumableEffect(type="consumable", effect="heal", amount=10),
    )
    fresh_state.items["sword_01"] = Item(id="sword_01", name="단검")
    fresh_state.characters["player_01"] = Character(
        id="player_01",
        name="주인공",
        race_id="human",
        is_player=True,
        location_id="plaza_01",
        stats=Stats(),
        max_hp=20,
        hp=20,  # full HP — heal will be rejected
        inventory_ids=["herb_01", "sword_01"],
    )
    return fresh_state


async def _collect(it):
    return [ev async for ev in it]


async def test_chain_passes_skipped_heal_notice_into_narrate(
    state_full_hp_with_heal,
    tmp_saves,
    monkeypatch,
):
    """When chain.parts has a heal that gets skipped (full HP) followed by a
    PassAction tail, the engine notice from the skipped heal must reach
    narrate via `act_log_lines` so the body can reflect "이미 체력 가득"
    instead of describing a successful drink."""
    captured_kw: dict = {}

    async def fake_run_narrate(*a, **kw):
        captured_kw.update(kw)
        if False:
            yield None  # pragma: no cover — make it an async generator

    monkeypatch.setattr(narrate_mod, "run_narrate", fake_run_narrate)

    async def fake_judge(*a, **kw):
        return JudgeOutput(actions=[
            Verb(name="use", modifiers={"item_id": "herb_01"}),
            Verb(name="transfer", modifiers={
                "from_id": "<self>.inventory", "to_id": "<self>.equipped.weapon",
                "mode": "gift", "item_id": "sword_01",
            }),
            Verb(name="wait"),
        ])

    monkeypatch.setattr(turn_mod, "run_judge", fake_judge)

    await _collect(
        run_turn(
            client=None,
            state=state_full_hp_with_heal,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_saves)),
            player_input="약초 먹고 단검 든다",
        )
    )

    lines = captured_kw.get("act_log_lines") or []
    assert any("체력이 가득" in line for line in lines), (
        f"expected heal-skip notice in act_log_lines, got {lines}"
    )
    # The equip succeeded — its act log line should also be carried so narrate
    # knows what *did* happen, not just what was skipped.
    assert any("단검" in line for line in lines), (
        f"expected equip notice in act_log_lines, got {lines}"
    )


async def test_non_chain_pass_passes_empty_act_log_lines(
    state_full_hp_with_heal,
    tmp_saves,
    monkeypatch,
):
    """Plain PassAction (not chain) gives narrate an empty list — the slot
    is chain-only signal."""
    captured_kw: dict = {}

    async def fake_run_narrate(*a, **kw):
        captured_kw.update(kw)
        if False:
            yield None  # pragma: no cover

    monkeypatch.setattr(narrate_mod, "run_narrate", fake_run_narrate)

    async def fake_judge(*a, **kw):
        return JudgeOutput(actions=[Verb(name="wait")])

    monkeypatch.setattr(turn_mod, "run_judge", fake_judge)

    await _collect(
        run_turn(
            client=None,
            state=state_full_hp_with_heal,
            scenario_repo=LocalFsScenarioRepo(profile_dir="<unused>"),
            save_repo=LocalFsSaveRepo(saves_dir=str(tmp_saves)),
            player_input="잠시 둘러본다",
        )
    )

    # Either the key is missing (None) or it's an empty list — both mean
    # "no chain notices to reflect". Truthy non-empty would be wrong.
    assert not captured_kw.get("act_log_lines")
